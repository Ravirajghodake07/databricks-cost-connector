from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .client import create_workspace_client
from .collectors import CollectionResult, SystemTableCollector
from .config import load_settings
from .coverage import build_coverage_row, synthetic_result
from .discovery import (
    classify_error_kind,
    list_system_tables,
    plan_collection,
    with_discovery_failure,
)
from .models import CollectionStatus
from .normalizer import apply_list_cost, normalize_records
from .output import (
    write_coverage_report,
    write_normalized_records,
    write_raw_records,
)


OUTPUT_DIR = Path("output")


def find_warehouse(client, warehouse_name: str):
    warehouses = list(client.warehouses.list())
    for warehouse in warehouses:
        if warehouse.name == warehouse_name:
            return warehouse
    raise RuntimeError(
        f"SQL warehouse '{warehouse_name}' was not found."
    )


def _dump_normalized(records: list[Any]) -> list[dict[str, Any]]:
    return [item.model_dump(mode="json") for item in records]


def collect_dataset(
    collector: SystemTableCollector,
    planned: Any,
) -> tuple[CollectionResult, list[Any], list[str]]:
    if planned.status is not None:
        result = synthetic_result(
            planned.spec,
            planned.status,
            planned.error,
        )
        return result, [], []

    result = collector.collect(planned.spec)
    normalized, errors = normalize_records(
        planned.spec.source,
        result.records,
        result.collected_at,
    )
    return result, normalized, errors


def main() -> None:
    settings = load_settings()
    client = create_workspace_client(settings)

    try:
        client.current_user.me()
    except Exception as exc:
        message = str(exc)
        print("Authentication failed: credentials were rejected or unavailable.")
        print(f"Authentication error kind: {classify_error_kind(message)}")
        raise SystemExit(1) from exc

    print("Authentication succeeded.")

    warehouse = find_warehouse(client, settings.warehouse_name)

    print(f"Using warehouse: {warehouse.name}")
    print(f"Warehouse state: {warehouse.state}")
    if settings.start_time:
        print(f"Collection start time: {settings.start_time.isoformat()}")
    else:
        print("Collection start time: unbounded")
    if settings.end_time:
        print(f"Collection end time: {settings.end_time.isoformat()}")
    else:
        print("Collection end time: unbounded")
    print()
    print("Discovering system tables...")

    discovered, discovery_error = list_system_tables(client)
    planned = plan_collection(discovered, discovery_error)
    if discovery_error:
        print(f"Discovery listing warning: {discovery_error}")
        planned = with_discovery_failure(planned, discovery_error)
    else:
        print(f"Discovered {len(discovered)} system tables.")
    print("Starting Databricks system-table collection...")
    print()

    collector = SystemTableCollector(
        client=client,
        warehouse_id=warehouse.id,
        settings=settings,
    )

    
    coverage_rows: list[dict[str, Any]] = []
    usage_normalized: list[Any] = []
    price_normalized: list[Any] = []
    usage_result: CollectionResult | None = None
    normalization_error_count = 0


    for item in planned:
        started = datetime.now(timezone.utc)
        try:
            result, normalized, errors = collect_dataset(collector, item)
        except Exception as exc:
            result = CollectionResult(
                dataset=item.spec,
                status=CollectionStatus.FAILED,
                records=[],
                record_count=0,
                collected_at=datetime.now(timezone.utc),
                error=str(exc),
            )
            normalized, errors = [], []

        if item.spec.source == "system.billing.usage":
            usage_normalized = list(normalized)
            usage_result = result
        elif item.spec.source == "system.billing.list_prices":
            price_normalized = list(normalized)

        raw_path = None
        normalized_path = None
        if result.records:
            raw_path = write_raw_records(
                OUTPUT_DIR,
                item.spec.source,
                result.records,
            )

        if (
            item.spec.source == "system.billing.usage"
            and normalized
            and price_normalized
        ):
            normalized = [
                apply_list_cost(record, price_normalized)
                for record in normalized
            ]
            usage_normalized = list(normalized)

        if normalized:
            normalized_path = write_normalized_records(
                OUTPUT_DIR,
                item.spec.source,
                _dump_normalized(normalized),
            )

        row = build_coverage_row(
            result,
            discovered=item.discovered,
            collection_started_at=started,
            normalized_record_count=len(normalized),
            raw_output=str(raw_path) if raw_path else None,
            normalized_output=str(normalized_path) if normalized_path else None,
        )
        if errors:
            normalization_error_count += len(errors)
            row["normalization_errors"] = errors[:20]
        coverage_rows.append(row)
        print(
            f"{item.spec.source} {result.status} {result.record_count}"
        )

    if (
        usage_result
        and usage_normalized
        and price_normalized
        and usage_result.records
    ):
        write_normalized_records(
            OUTPUT_DIR,
            "system.billing.usage",
            _dump_normalized(usage_normalized),
        )

    
    coverage_path = write_coverage_report(OUTPUT_DIR, coverage_rows)

    print()
    print(f"Normalization errors: {normalization_error_count}")
    print(coverage_path)
    print("Collection complete.")



if __name__ == "__main__":
    main()
