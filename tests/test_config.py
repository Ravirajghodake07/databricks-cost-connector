from datetime import datetime, timezone

import pytest

from src.databricks_cost_connector.config import (
    Settings,
    load_settings,
    parse_datetime,
)


def set_required_environment(monkeypatch):
    monkeypatch.setenv(
        "DATABRICKS_HOST",
        "https://example.databricks.com",
    )
    monkeypatch.setenv("DATABRICKS_TOKEN", "test-token")


def test_parse_datetime_accepts_utc_z():
    result = parse_datetime(
        "2026-10-01T12:30:00Z",
        "DATABRICKS_START_TIME",
    )

    assert result == datetime(2026, 10, 1, 12, 30, tzinfo=timezone.utc)


def test_parse_datetime_converts_offset_to_utc():
    result = parse_datetime(
        "2026-10-01T15:30:00+03:00",
        "DATABRICKS_START_TIME",
    )

    assert result == datetime(2026, 10, 1, 12, 30, tzinfo=timezone.utc)


def test_parse_datetime_assumes_utc_when_timezone_missing():
    result = parse_datetime(
        "2026-10-01T12:30:00",
        "DATABRICKS_START_TIME",
    )

    assert result == datetime(2026, 10, 1, 12, 30, tzinfo=timezone.utc)


def test_parse_datetime_returns_none_for_empty_value():
    assert parse_datetime(None, "DATABRICKS_START_TIME") is None
    assert parse_datetime("", "DATABRICKS_START_TIME") is None


def test_parse_datetime_rejects_invalid_value():
    with pytest.raises(
        ValueError,
        match="DATABRICKS_START_TIME must be an ISO-8601 timestamp",
    ):
        parse_datetime("not-a-date", "DATABRICKS_START_TIME")


def test_load_settings_requires_host(monkeypatch):
    from src.databricks_cost_connector import config

    monkeypatch.setattr(config, "load_dotenv", lambda: None)
    monkeypatch.delenv("DATABRICKS_HOST", raising=False)
    monkeypatch.setenv("DATABRICKS_TOKEN", "test-token")

    with pytest.raises(
        ValueError,
        match="DATABRICKS_HOST is not configured",
    ):
        load_settings()


def test_load_settings_requires_token(monkeypatch):
    from src.databricks_cost_connector import config

    monkeypatch.setattr(config, "load_dotenv", lambda: None)
    monkeypatch.setenv(
        "DATABRICKS_HOST",
        "https://example.databricks.com",
    )
    monkeypatch.delenv("DATABRICKS_TOKEN", raising=False)

    with pytest.raises(
        ValueError,
        match="DATABRICKS_TOKEN is not configured",
    ):
        load_settings()


def test_load_settings_uses_default_warehouse(monkeypatch):
    set_required_environment(monkeypatch)
    monkeypatch.delenv("DATABRICKS_WAREHOUSE_NAME", raising=False)
    monkeypatch.delenv("DATABRICKS_START_TIME", raising=False)
    monkeypatch.delenv("DATABRICKS_END_TIME", raising=False)

    settings = load_settings()

    assert settings.warehouse_name == "Serverless Starter Warehouse"
    assert settings.start_time is None
    assert settings.end_time is None


def test_load_settings_reads_custom_warehouse_and_time_window(monkeypatch):
    set_required_environment(monkeypatch)
    monkeypatch.setenv("DATABRICKS_WAREHOUSE_NAME", "Test Warehouse")
    monkeypatch.setenv("DATABRICKS_START_TIME", "2026-10-01T00:00:00Z")
    monkeypatch.setenv("DATABRICKS_END_TIME", "2026-10-05T00:00:00Z")

    settings = load_settings()

    assert settings.warehouse_name == "Test Warehouse"
    assert settings.start_time == datetime(
        2026, 10, 1, tzinfo=timezone.utc
    )
    assert settings.end_time == datetime(
        2026, 10, 5, tzinfo=timezone.utc
    )


def test_load_settings_rejects_invalid_time_range(monkeypatch):
    set_required_environment(monkeypatch)
    monkeypatch.setenv("DATABRICKS_START_TIME", "2026-10-05T00:00:00Z")
    monkeypatch.setenv("DATABRICKS_END_TIME", "2026-10-01T00:00:00Z")

    with pytest.raises(
        ValueError,
        match="DATABRICKS_START_TIME must be earlier than DATABRICKS_END_TIME",
    ):
        load_settings()


def test_load_settings_rejects_equal_time_boundaries(monkeypatch):
    set_required_environment(monkeypatch)
    monkeypatch.setenv("DATABRICKS_START_TIME", "2026-10-01T00:00:00Z")
    monkeypatch.setenv("DATABRICKS_END_TIME", "2026-10-01T00:00:00Z")

    with pytest.raises(
        ValueError,
        match="DATABRICKS_START_TIME must be earlier than DATABRICKS_END_TIME",
    ):
        load_settings()


def test_settings_is_immutable():
    settings = Settings(
        databricks_host="https://example.databricks.com",
        databricks_token="test-token",
    )

    with pytest.raises(AttributeError):
        settings.warehouse_name = "Changed Warehouse"
