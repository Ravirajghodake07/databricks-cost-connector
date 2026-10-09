from __future__ import annotations

import re
import time

from databricks.sdk.errors import DatabricksError
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from databricks.sdk import WorkspaceClient

from .config import Settings
from .discovery import (
    TIME_FILTER_INTERVAL,
    TIME_FILTER_POINT,
    TIME_FILTER_PRICE,
    DatasetSpec,
    classify_error_kind,
    classify_status_message,
)
from .models import CollectionStatus


IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass
class CollectionResult:
    dataset: DatasetSpec
    status: str
    records: list[dict[str, Any]]
    record_count: int
    collected_at: datetime
    error: str | None = None
    error_kind: str | None = None


class SystemTableCollector:
    def __init__(
        self,
        client: WorkspaceClient,
        settings: Settings,
        warehouse_id: str,
    ) -> None:
        self.client = client
        self.settings = settings
        self.warehouse_id = warehouse_id

    def collect(self, dataset: DatasetSpec) -> CollectionResult:
        try:
            statement = self._build_statement(dataset)

            response = self.client.statement_execution.execute_statement(
                statement=statement,
                warehouse_id=self.warehouse_id,
                wait_timeout="50s",
            )
            response = self._wait_for_completion(response)

            collected_at = datetime.now(timezone.utc)

            return self._collection_from_response(
                dataset,
                collected_at,
                response,
            )

        except Exception as exc:
            collected_at = datetime.now(timezone.utc)
            message = str(exc)

            return CollectionResult(
                dataset=dataset,
                status=classify_status_message(message),
                records=[],
                record_count=0,
                collected_at=collected_at,
                error=message,
                error_kind=classify_error_kind(message),
            )

    def _build_statement(self, dataset: DatasetSpec) -> str:
        source = quote_table_name(dataset.source)
        predicates: list[str] = []

        time_filter = getattr(dataset, "time_filter", None)
        time_columns = getattr(dataset, "time_columns", None)

        # Tests and ad-hoc DatasetSpec instances may omit the optional
        # time-filter metadata. Preserve the connector's known source rules
        # in that case.
        if time_filter is None and time_columns is None:
            source_rules = {
                "system.billing.usage": (
                    TIME_FILTER_INTERVAL,
                    ("usage_start_time", "usage_end_time"),
                ),
                "system.billing.list_prices": (
                    TIME_FILTER_PRICE,
                    ("price_start_time", "price_end_time"),
                ),
                "system.query.history": (
                    TIME_FILTER_INTERVAL,
                    ("start_time", "end_time"),
                ),
                "system.compute.warehouse_events": (
                    TIME_FILTER_POINT,
                    ("event_time", None),
                ),
            }
            rule = source_rules.get(dataset.source)
            if rule is not None:
                time_filter, time_columns = rule

        if time_columns:
            start_column, end_column = time_columns

            if time_filter == TIME_FILTER_PRICE:
                predicates.extend(
                    self._price_predicates_from_columns(
                        start_column,
                        end_column,
                    )
                )
            elif time_filter == TIME_FILTER_POINT:
                predicates.extend(
                    self._point_predicates_from_columns(start_column)
                )
            elif time_filter == TIME_FILTER_INTERVAL:
                predicates.extend(
                    self._interval_predicates_from_columns(
                        start_column,
                        end_column,
                    )
                )
            elif time_filter is None:
                # A DatasetSpec can carry columns without a time-filter enum.
                # Treat an interval pair as an interval and a single column
                # as a point-in-time source.
                if end_column:
                    predicates.extend(
                        self._interval_predicates_from_columns(
                            start_column,
                            end_column,
                        )
                    )
                else:
                    predicates.extend(
                        self._point_predicates_from_columns(start_column)
                    )

        if not predicates:
            return f"SELECT * FROM {source}"

        return f"SELECT * FROM {source} WHERE {' AND '.join(predicates)}"

    def _interval_predicates(
        self,
        dataset: DatasetSpec,
    ) -> list[str]:
        start_column, end_column = dataset.time_columns or (None, None)
        if not start_column:
            return []
        return self._interval_predicates_from_columns(
            start_column,
            end_column,
        )

    def _interval_predicates_from_columns(
        self,
        start_column: str,
        end_column: str | None,
    ) -> list[str]:
        predicates: list[str] = []

        if self.settings.start_time is not None:
            start_literal = _sql_timestamp_literal(
                self.settings.start_time
            )
            if end_column:
                predicates.append(
                    f"{end_column} >= {start_literal}"
                )

        if self.settings.end_time is not None:
            end_literal = _sql_timestamp_literal(
                self.settings.end_time
            )
            predicates.append(
                f"{start_column} < {end_literal}"
            )

        return predicates

    def _point_predicates(self, dataset: DatasetSpec) -> list[str]:
        start_column, _ = dataset.time_columns or (None, None)
        if not start_column:
            return []
        return self._point_predicates_from_columns(start_column)

    def _point_predicates_from_columns(
        self,
        point_column: str,
    ) -> list[str]:
        predicates: list[str] = []

        if self.settings.start_time is not None:
            predicates.append(
                f"{point_column} >= "
                f"{_sql_timestamp_literal(self.settings.start_time)}"
            )

        if self.settings.end_time is not None:
            predicates.append(
                f"{point_column} < "
                f"{_sql_timestamp_literal(self.settings.end_time)}"
            )

        return predicates

    def _price_predicates(self, dataset: DatasetSpec) -> list[str]:
        start_column, end_column = dataset.time_columns or (None, None)
        if not start_column:
            return []
        return self._price_predicates_from_columns(
            start_column,
            end_column,
        )

    def _price_predicates_from_columns(
        self,
        start_column: str,
        end_column: str | None,
    ) -> list[str]:
        predicates: list[str] = []

        if self.settings.start_time is not None:
            start_literal = _sql_timestamp_literal(
                self.settings.start_time
            )
            if end_column:
                predicates.append(
                    f"({end_column} IS NULL OR "
                    f"{end_column} >= {start_literal})"
                )

        if self.settings.end_time is not None:
            end_literal = _sql_timestamp_literal(
                self.settings.end_time
            )
            predicates.append(
                f"{start_column} < {end_literal}"
            )

        return predicates

    def _wait_for_completion(self, response: Any) -> Any:
        status = getattr(response, "status", None)

        # Test doubles and some response shapes do not expose a status.
        if status is None:
            return response

        state_name = _status_name(status)

        if state_name in {
            "SUCCEEDED",
            "FAILED",
            "CANCELED",
            "CANCELLED",
        }:
            return response

        for _ in range(120):
            time.sleep(1)

            statement_id = getattr(response, "statement_id", None)
            if not statement_id:
                return response

            response = self.client.statement_execution.get_statement(
                statement_id
            )

            state_name = _status_name(
                getattr(response, "status", None)
            )

            if state_name in {
                "SUCCEEDED",
                "FAILED",
                "CANCELED",
                "CANCELLED",
            }:
                return response

        raise TimeoutError("Databricks statement execution timed out.")

    def _collection_from_response(
        self,
        dataset: DatasetSpec,
        collected_at: datetime,
        response: Any,
    ) -> CollectionResult:
        state_name = _status_name(
            getattr(response, "status", None)
        )

        if state_name in {
            "FAILED",
            "CANCELED",
            "CANCELLED",
        }:
            error_message = _extract_statement_error(response)

            return CollectionResult(
                dataset=dataset,
                status=classify_status_message(error_message),
                records=[],
                record_count=0,
                collected_at=collected_at,
                error=error_message,
                error_kind=classify_error_kind(error_message),
            )

        records = self._extract_all_records(response)

        if not records:
            return CollectionResult(
                dataset=dataset,
                status=CollectionStatus.EMPTY,
                records=[],
                record_count=0,
                collected_at=collected_at,
            )

        return CollectionResult(
            dataset=dataset,
            status=CollectionStatus.COLLECTED,
            records=records,
            record_count=len(records),
            collected_at=collected_at,
        )

    def _extract_all_records(
        self,
        response: Any,
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []

        result = getattr(response, "result", None)
        if result is None:
            return records

        manifest = getattr(response, "manifest", None)
        schema = getattr(manifest, "schema", None)
        if schema is None:
            schema = getattr(result, "schema", None)

        columns = _column_names(schema)

        records.extend(
            _rows_from_result(
                result,
                columns=columns,
            )
        )

        next_chunk_index = getattr(
            result,
            "next_chunk_index",
            None,
        )

        statement_id = getattr(response, "statement_id", None)

        while next_chunk_index is not None:
            if not statement_id:
                break

            chunk = self._get_result_chunk(
                statement_id,
                next_chunk_index,
            )

            records.extend(
                _rows_from_result(
                    chunk,
                    columns=columns,
                )
            )

            next_chunk_index = getattr(
                chunk,
                "next_chunk_index",
                None,
            )

        return records


    def _get_result_chunk(
        self,
        statement_id: str,
        chunk_index: int,
    ) -> Any:
        statement_api = self.client.statement_execution

        get_chunk_n = getattr(
            statement_api,
            "get_statement_result_chunk_n",
            None,
        )

        get_chunk = getattr(
            statement_api,
            "get_statement_result_chunk",
            None,
        )

        if get_chunk_n is None and get_chunk is None:
            raise AttributeError(
                "Databricks statement execution client does not expose "
                "a supported result-chunk method."
            )

        max_attempts = 3

        for attempt in range(max_attempts):
            try:
                if get_chunk_n is not None:
                    return get_chunk_n(statement_id, chunk_index)

                try:
                    return get_chunk(
                        statement_id=statement_id,
                        chunk_index=chunk_index,
                    )
                except TypeError:
                    return get_chunk(statement_id, chunk_index)

            except Exception as exc:
                message = str(exc).lower()

                permanent_markers = (
                    "permission_denied",
                    "unauthorized",
                    "forbidden",
                    "invalid_parameter",
                    "invalid_argument",
                    "not found",
                )

                is_permanent = (
                    isinstance(exc, DatabricksError)
                    and getattr(exc, "error_code", None)
                    is not None
                    and str(exc.error_code).upper()
                    not in {
                        "INTERNAL_ERROR",
                        "TEMPORARILY_UNAVAILABLE",
                        "TOO_MANY_REQUESTS",
                    }
                ) or any(
                    marker in message
                    for marker in permanent_markers
                )

                if is_permanent or attempt == max_attempts - 1:
                    raise

                retry_after = getattr(exc, "retry_after_secs", None)
                delay = (
                    min(max(float(retry_after), 0.0), 5.0)
                    if retry_after is not None
                    else 0.5 * (2 ** attempt)
                )
                time.sleep(delay)

        raise RuntimeError("Result chunk retrieval failed unexpectedly.")


def quote_table_name(source: str) -> str:
    parts = source.split(".")
    quoted: list[str] = []

    for part in parts:
        if not IDENT_RE.fullmatch(part):
            raise ValueError(
                f"Refusing to query unsafe identifier: {source}"
            )
        quoted.append(part)

    return ".".join(quoted)


def _status_name(status: Any) -> str | None:
    if status is None:
        return None

    state = getattr(status, "state", status)
    if state is None:
        return None

    value = getattr(state, "value", state)
    return str(value).upper()


def _extract_statement_error(response: Any) -> str:
    status = getattr(response, "status", None)
    error = getattr(status, "error", None)

    if error is None:
        error = getattr(response, "error", None)

    if error is None:
        return "Databricks statement execution failed."

    error_message = getattr(error, "message", None)
    if error_message:
        return str(error_message)

    return str(error)


def _rows_from_result(
    result: Any,
    columns: list[str] | None = None,
) -> list[dict[str, Any]]:
    if result is None:
        return []

    if columns is None:
        columns = _column_names(
            getattr(result, "schema", None)
        )

    data = getattr(result, "data_array", None)
    if data is None:
        data = getattr(result, "data", None)

    if data is None:
        return []

    records: list[dict[str, Any]] = []

    for row in data:
        if isinstance(row, dict):
            records.append(dict(row))
            continue

        values = _row_values(row)
        record: dict[str, Any] = {}

        for index, column in enumerate(columns):
            record[column] = (
                values[index]
                if index < len(values)
                else None
            )

        records.append(record)

    return records


def _column_names(schema: Any) -> list[str]:
    if schema is None:
        return []

    columns = getattr(schema, "columns", None)
    if columns is None:
        return []

    names: list[str] = []

    for column in columns:
        if isinstance(column, str):
            names.append(column)
            continue

        name = getattr(column, "name", None)
        if name is None:
            name = getattr(column, "column_name", None)

        if name is not None:
            names.append(str(name))

    return names


def _row_values(row: Any) -> list[Any]:
    if isinstance(row, (list, tuple)):
        return list(row)

    values = getattr(row, "values", None)
    if values is not None:
        if callable(values):
            values = values()
        if isinstance(values, (list, tuple)):
            return list(values)

    return [row]


def _sql_timestamp_literal(value: datetime) -> str:
    normalized = value

    if normalized.tzinfo is None:
        normalized = normalized.replace(
            tzinfo=timezone.utc
        )

    normalized = normalized.astimezone(timezone.utc)
    formatted = normalized.strftime(
        "%Y-%m-%d %H:%M:%S.%f"
    )

    return f"TIMESTAMP '{formatted}'"
