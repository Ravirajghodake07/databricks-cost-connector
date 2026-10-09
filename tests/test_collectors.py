from datetime import datetime, timezone

import pytest

from src.databricks_cost_connector.collectors import SystemTableCollector
from src.databricks_cost_connector.config import Settings
from src.databricks_cost_connector.discovery import (
    DatasetSpec,
    list_system_tables,
)


class FakeStatement:
    def __init__(self, statement_id: str = "statement-123"):
        self.statement_id = statement_id


class FakeStatementsAPI:
    def __init__(self):
        self.executed_statement = None

    def execute_statement(self, **kwargs):
        self.executed_statement = kwargs
        return FakeStatement()


class FakeWorkspaceClient:
    def __init__(self):
        self.statement_execution = FakeStatementsAPI()


def make_dataset(source: str) -> DatasetSpec:
    return DatasetSpec(
        category=source.split(".")[1],
        purpose=f"Test dataset for {source}",
        source=source,
        required_capability="test capability",
        normalizable=False,
    )


def make_settings(
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> Settings:
    return Settings(
        databricks_host="https://example.databricks.com",
        databricks_token="token",
        warehouse_name="Test Warehouse",
        start_time=start_time,
        end_time=end_time,
    )


def make_collector(settings: Settings | None = None):
    if settings is None:
        settings = make_settings()

    client = FakeWorkspaceClient()

    collector = SystemTableCollector(
        client=client,
        warehouse_id="warehouse-123",
        settings=settings,
    )

    return collector, client


def test_no_time_window_preserves_full_query():
    collector, _ = make_collector()

    statement = collector._build_statement(
        make_dataset("system.billing.usage")
    )

    assert statement == "SELECT * FROM system.billing.usage"


def test_billing_usage_start_and_end_time_filter():
    settings = make_settings(
        start_time=datetime(2026, 10, 1, tzinfo=timezone.utc),
        end_time=datetime(2026, 10, 5, tzinfo=timezone.utc),
    )

    collector, _ = make_collector(settings=settings)

    statement = collector._build_statement(
        make_dataset("system.billing.usage")
    )

    assert (
        "usage_end_time >= TIMESTAMP '2026-10-01 00:00:00.000000'"
        in statement
    )

    assert (
        "usage_start_time < TIMESTAMP '2026-10-05 00:00:00.000000'"
        in statement
    )


def test_billing_list_prices_start_and_end_time_filter():
    settings = make_settings(
        start_time=datetime(2026, 10, 1, tzinfo=timezone.utc),
        end_time=datetime(2026, 10, 5, tzinfo=timezone.utc),
    )

    collector, _ = make_collector(settings=settings)

    statement = collector._build_statement(
        make_dataset("system.billing.list_prices")
    )

    assert (
        "(price_end_time IS NULL OR price_end_time >= "
        "TIMESTAMP '2026-10-01 00:00:00.000000')"
        in statement
    )

    assert (
        "price_start_time < TIMESTAMP '2026-10-05 00:00:00.000000'"
        in statement
    )


def test_query_history_start_and_end_time_filter():
    settings = make_settings(
        start_time=datetime(2026, 10, 1, tzinfo=timezone.utc),
        end_time=datetime(2026, 10, 5, tzinfo=timezone.utc),
    )

    collector, _ = make_collector(settings=settings)

    statement = collector._build_statement(
        make_dataset("system.query.history")
    )

    # Query history is an interval, so records are included when
    # their query interval overlaps the requested collection window.
    assert (
        "end_time >= TIMESTAMP '2026-10-01 00:00:00.000000'"
        in statement
    )

    assert (
        "start_time < TIMESTAMP '2026-10-05 00:00:00.000000'"
        in statement
    )


def test_warehouse_events_use_event_time():
    settings = make_settings(
        start_time=datetime(2026, 10, 1, tzinfo=timezone.utc),
        end_time=datetime(2026, 10, 5, tzinfo=timezone.utc),
    )

    collector, _ = make_collector(settings=settings)

    statement = collector._build_statement(
        make_dataset("system.compute.warehouse_events")
    )

    assert (
        "event_time >= TIMESTAMP '2026-10-01 00:00:00.000000'"
        in statement
    )

    assert (
        "event_time < TIMESTAMP '2026-10-05 00:00:00.000000'"
        in statement
    )


def test_metadata_dataset_is_not_time_filtered():
    settings = make_settings(
        start_time=datetime(2026, 10, 1, tzinfo=timezone.utc),
        end_time=datetime(2026, 10, 5, tzinfo=timezone.utc),
    )

    collector, _ = make_collector(settings=settings)

    statement = collector._build_statement(
        make_dataset("system.compute.node_types")
    )

    assert statement == "SELECT * FROM system.compute.node_types"


def test_invalid_time_range_is_rejected(monkeypatch):
    from src.databricks_cost_connector.config import load_settings

    monkeypatch.setenv(
        "DATABRICKS_HOST",
        "https://example.databricks.com",
    )

    monkeypatch.setenv(
        "DATABRICKS_TOKEN",
        "token",
    )

    monkeypatch.setenv(
        "DATABRICKS_START_TIME",
        "2026-10-05T00:00:00Z",
    )

    monkeypatch.setenv(
        "DATABRICKS_END_TIME",
        "2026-10-01T00:00:00Z",
    )

    with pytest.raises(ValueError):
        load_settings()


def test_start_time_only():
    settings = make_settings(
        start_time=datetime(2026, 10, 1, tzinfo=timezone.utc),
    )

    collector, _ = make_collector(settings=settings)

    statement = collector._build_statement(
        make_dataset("system.billing.usage")
    )

    assert (
        "usage_end_time >= TIMESTAMP '2026-10-01 00:00:00.000000'"
        in statement
    )

    assert "usage_start_time <" not in statement


def test_end_time_only():
    settings = make_settings(
        end_time=datetime(2026, 10, 5, tzinfo=timezone.utc),
    )

    collector, _ = make_collector(settings=settings)

    statement = collector._build_statement(
        make_dataset("system.billing.usage")
    )

    assert (
        "usage_start_time < TIMESTAMP '2026-10-05 00:00:00.000000'"
        in statement
    )

    assert "usage_end_time >=" not in statement


def test_time_window_is_converted_to_utc():
    settings = make_settings(
        start_time=datetime(
            2026,
            10,
            1,
            5,
            30,
            tzinfo=timezone.utc,
        ),
        end_time=datetime(
            2026,
            10,
            2,
            5,
            30,
            tzinfo=timezone.utc,
        ),
    )

    collector, _ = make_collector(settings=settings)

    statement = collector._build_statement(
        make_dataset("system.billing.usage")
    )

    assert (
        "2026-10-01 05:30:00.000000"
        in statement
    )

    assert (
        "2026-10-02 05:30:00.000000"
        in statement
    )


def test_other_dataset_remains_unfiltered():
    settings = make_settings(
        start_time=datetime(2026, 10, 1, tzinfo=timezone.utc),
        end_time=datetime(2026, 10, 5, tzinfo=timezone.utc),
    )

    collector, _ = make_collector(settings=settings)

    statement = collector._build_statement(
        make_dataset("system.access.audit")
    )

    assert statement == "SELECT * FROM system.access.audit"


def test_statement_uses_configured_warehouse():
    settings = make_settings()

    collector, client = make_collector(settings=settings)

    dataset = make_dataset("system.billing.usage")

    collector.collect(dataset)

    assert client.statement_execution.executed_statement is not None

    assert (
        client.statement_execution.executed_statement["warehouse_id"]
        == "warehouse-123"
    )


def test_statement_uses_generated_sql():
    settings = make_settings(
        start_time=datetime(2026, 10, 1, tzinfo=timezone.utc),
        end_time=datetime(2026, 10, 5, tzinfo=timezone.utc),
    )

    collector, client = make_collector(settings=settings)

    dataset = make_dataset("system.billing.usage")

    collector.collect(dataset)

    executed = client.statement_execution.executed_statement

    assert executed is not None

    assert (
        executed["statement"]
        == (
            "SELECT * FROM system.billing.usage "
            "WHERE usage_end_time >= "
            "TIMESTAMP '2026-10-01 00:00:00.000000' "
            "AND usage_start_time < "
            "TIMESTAMP '2026-10-05 00:00:00.000000'"
        )
    )


def test_no_time_window_statement_has_no_where_clause():
    collector, _ = make_collector(
        settings=make_settings()
    )

    statement = collector._build_statement(
        make_dataset("system.query.history")
    )

    assert statement == "SELECT * FROM system.query.history"
    assert "WHERE" not in statement


def test_billing_usage_supports_only_start_boundary():
    settings = make_settings(
        start_time=datetime(
            2026,
            10,
            3,
            tzinfo=timezone.utc,
        )
    )

    collector, _ = make_collector(settings=settings)

    statement = collector._build_statement(
        make_dataset("system.billing.usage")
    )

    assert (
        "usage_end_time >= TIMESTAMP '2026-10-03 00:00:00.000000'"
        in statement
    )

    assert "usage_start_time <" not in statement


def test_billing_usage_supports_only_end_boundary():
    settings = make_settings(
        end_time=datetime(
            2026,
            10,
            4,
            tzinfo=timezone.utc,
        )
    )

    collector, _ = make_collector(settings=settings)

    statement = collector._build_statement(
        make_dataset("system.billing.usage")
    )

    assert (
        "usage_start_time < TIMESTAMP '2026-10-04 00:00:00.000000'"
        in statement
    )

    assert "usage_end_time >=" not in statement


def test_list_prices_uses_both_boundaries():
    settings = make_settings(
        start_time=datetime(
            2026,
            10,
            1,
            tzinfo=timezone.utc,
        ),
        end_time=datetime(
            2026,
            10,
            5,
            tzinfo=timezone.utc,
        ),
    )

    collector, _ = make_collector(settings=settings)

    statement = collector._build_statement(
        make_dataset("system.billing.list_prices")
    )

    assert "price_end_time IS NULL OR price_end_time >=" in statement
    assert "price_start_time <" in statement


def test_query_history_uses_interval_overlap():
    settings = make_settings(
        start_time=datetime(
            2026,
            10,
            1,
            tzinfo=timezone.utc,
        ),
        end_time=datetime(
            2026,
            10,
            5,
            tzinfo=timezone.utc,
        ),
    )

    collector, _ = make_collector(settings=settings)

    statement = collector._build_statement(
        make_dataset("system.query.history")
    )

    assert "end_time >=" in statement
    assert "start_time <" in statement


def test_warehouse_events_use_half_open_window():
    settings = make_settings(
        start_time=datetime(
            2026,
            10,
            1,
            tzinfo=timezone.utc,
        ),
        end_time=datetime(
            2026,
            10,
            5,
            tzinfo=timezone.utc,
        ),
    )

    collector, _ = make_collector(settings=settings)

    statement = collector._build_statement(
        make_dataset("system.compute.warehouse_events")
    )

    assert "event_time >=" in statement
    assert "event_time <" in statement


def test_unrelated_dataset_does_not_receive_time_filter():
    settings = make_settings(
        start_time=datetime(
            2026,
            10,
            1,
            tzinfo=timezone.utc,
        ),
        end_time=datetime(
            2026,
            10,
            5,
            tzinfo=timezone.utc,
        ),
    )

    collector, _ = make_collector(settings=settings)

    datasets = [
        "system.compute.node_types",
        "system.compute.warehouses",
        "system.access.audit",
        "system.access.workspaces_latest",
        "system.lakeflow.jobs",
    ]

    for source in datasets:
        statement = collector._build_statement(
            make_dataset(source)
        )

        assert statement == f"SELECT * FROM {source}"


def test_start_and_end_are_optional():
    settings = make_settings()

    assert settings.start_time is None
    assert settings.end_time is None


def test_timezone_aware_settings_are_preserved():
    start = datetime(
        2026,
        10,
        1,
        12,
        0,
        tzinfo=timezone.utc,
    )

    end = datetime(
        2026,
        10,
        2,
        12,
        0,
        tzinfo=timezone.utc,
    )

    settings = make_settings(
        start_time=start,
        end_time=end,
    )

    assert settings.start_time == start
    assert settings.end_time == end


def test_open_ended_list_prices_are_not_excluded_by_start_bound():
    settings = make_settings(
        start_time=datetime(2026, 10, 1, tzinfo=timezone.utc),
    )

    collector, _ = make_collector(settings=settings)

    statement = collector._build_statement(
        make_dataset("system.billing.list_prices")
    )

    assert "price_end_time IS NULL" in statement
    assert "price_end_time >=" in statement


def test_permission_error_is_classified(monkeypatch):
    collector, client = make_collector()

    def raise_permission(**kwargs):
        raise RuntimeError(
            "PERMISSION_DENIED: insufficient privileges"
        )

    client.statement_execution.execute_statement = raise_permission

    result = collector.collect(
        make_dataset("system.billing.usage")
    )

    assert result.status == "PERMISSION_DENIED"
    assert result.record_count == 0


def test_missing_table_is_classified_unavailable():
    collector, client = make_collector()

    def raise_missing(**kwargs):
        raise RuntimeError(
            "TABLE_OR_VIEW_NOT_FOUND: does not exist"
        )

    client.statement_execution.execute_statement = raise_missing

    result = collector.collect(
        make_dataset("system.billing.account_prices")
    )

    assert result.status == "UNAVAILABLE_IN_ACCOUNT"


def test_empty_result_is_empty_status():
    class Status:
        state = type(
            "S",
            (),
            {"value": "SUCCEEDED"},
        )()

        error = None

    class Column:
        def __init__(self, name):
            self.name = name

    class Schema:
        columns = [Column("record_id")]

    class Manifest:
        schema = Schema()
        total_chunk_count = 1

    class Result:
        data_array = []

    class Response:
        status = Status()
        result = Result()
        manifest = Manifest()
        statement_id = "s1"

    collector, client = make_collector()

    client.statement_execution.execute_statement = (
        lambda **kwargs: Response()
    )

    result = collector.collect(
        make_dataset("system.billing.usage")
    )

    assert result.status == "EMPTY"
    assert result.records == []


def test_pagination_retrieves_all_chunks():
    class Status:
        state = type(
            "S",
            (),
            {"value": "SUCCEEDED"},
        )()

        error = None

    class Column:
        def __init__(self, name):
            self.name = name

    class Schema:
        columns = [Column("record_id")]

    class Manifest:
        schema = Schema()
        total_chunk_count = 3

    class ResultChunk:
        def __init__(self, rows, next_index=None):
            self.data_array = rows
            self.next_chunk_index = next_index

    class Response:
        status = Status()
        result = ResultChunk(
            [["a"]],
            next_index=1,
        )
        manifest = Manifest()
        statement_id = "s1"

    chunks = {
        1: ResultChunk(
            [["b"]],
            next_index=2,
        ),
        2: ResultChunk(
            [["c"]],
            next_index=None,
        ),
    }

    class API:
        def execute_statement(self, **kwargs):
            return Response()

        def get_statement_result_chunk_n(
            self,
            statement_id,
            index,
        ):
            return chunks[index]

    collector, _ = make_collector()

    collector.client.statement_execution = API()

    result = collector.collect(
        make_dataset("system.billing.usage")
    )

    assert result.status == "COLLECTED"

    assert [
        row["record_id"]
        for row in result.records
    ] == ["a", "b", "c"]


def test_failed_sql_state_classifies_permission():
    class Error:
        def __str__(self):
            return "User is not authorized to SELECT"

    class Status:
        state = type(
            "S",
            (),
            {"value": "FAILED"},
        )()

        error = Error()

    class Response:
        status = Status()
        result = None
        manifest = None
        statement_id = "s1"

    collector, client = make_collector()

    client.statement_execution.execute_statement = (
        lambda **kwargs: Response()
    )

    result = collector.collect(
        make_dataset("system.compute.clusters")
    )

    assert result.status == "PERMISSION_DENIED"


def test_authentication_failure_is_classified():
    collector, client = make_collector()

    def raise_auth(**kwargs):
        raise RuntimeError(
            "401 Unauthorized: Invalid access token"
        )

    client.statement_execution.execute_statement = raise_auth

    result = collector.collect(
        make_dataset("system.billing.usage")
    )

    assert result.status == "FAILED"
    assert result.error_kind == "authentication"
    assert result.record_count == 0
    assert result.records == []


def test_list_system_tables_reports_schema_listing_failure():
    class FakeSchema:
        def __init__(self, name):
            self.name = name

    class FakeSchemasAPI:
        def list(self, **kwargs):
            return [
                FakeSchema("billing"),
                FakeSchema("compute"),
            ]

    class FakeTablesAPI:
        def list(self, catalog_name, schema_name):
            if schema_name == "billing":
                return [type("Table", (), {"name": "usage"})()]
            if schema_name == "compute":
                raise RuntimeError(
                    "PERMISSION_DENIED: access denied"
                )
            return []

    class FakeClient:
        schemas = FakeSchemasAPI()
        tables = FakeTablesAPI()

    discovered, error = list_system_tables(FakeClient())

    assert "system.billing.usage" in discovered
    assert error is not None
    assert "compute" in error
    assert "PERMISSION_DENIED" in error


def test_result_chunk_retries_transient_failure(monkeypatch):
    collector, client = make_collector()
    attempts = {"count": 0}

    class Chunk:
        data_array = [["a"]]
        next_chunk_index = None

    def flaky_fetch(statement_id, chunk_index):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("temporary connection error")
        return Chunk()

    client.statement_execution.get_statement_result_chunk_n = flaky_fetch

    monkeypatch.setattr(
        "src.databricks_cost_connector.collectors.time.sleep",
        lambda _: None,
    )

    chunk = collector._get_result_chunk("statement-123", 1)

    assert attempts["count"] == 2
    assert chunk.data_array == [["a"]]


def test_result_chunk_retry_exhaustion(monkeypatch):
    collector, client = make_collector()
    attempts = {"count": 0}

    def failing_fetch(statement_id, chunk_index):
        attempts["count"] += 1
        raise RuntimeError("temporary connection error")

    client.statement_execution.get_statement_result_chunk_n = failing_fetch

    monkeypatch.setattr(
        "src.databricks_cost_connector.collectors.time.sleep",
        lambda _: None,
    )

    import pytest

    with pytest.raises(RuntimeError, match="temporary connection error"):
        collector._get_result_chunk("statement-123", 1)

    assert attempts["count"] == 3
