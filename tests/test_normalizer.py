from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.databricks_cost_connector.normalizer import (
    apply_list_cost,
    normalize_billing_list_price,
    normalize_billing_usage,
    normalize_records,
    parse_decimal,
    parse_timestamp,
)


def make_usage_record() -> dict:
    """Create a representative billing usage fixture."""
    return {
        "account_id": "account-test",
        "workspace_id": "workspace-test",
        "record_id": "record-test",
        "sku_name": (
            "PREMIUM_SERVERLESS_SQL_COMPUTE_US_EAST_OHIO"
        ),
        "cloud": "AWS",
        "usage_start_time": (
            "2026-10-03T04:00:00.000Z"
        ),
        "usage_end_time": (
            "2026-10-03T05:00:00.000Z"
        ),
        "usage_date": "2026-10-03",
        "custom_tags": "{}",
        "usage_unit": "DBU",
        "usage_quantity": "5.083760000000000000",
        "usage_metadata": (
            '{"warehouse_id":"warehouse-test",'
            '"node_type":"db.small",'
            '"job_run_id":null,'
            '"job_name":null}'
        ),
        "identity_metadata": (
            '{"run_as":null,'
            '"created_by":null,'
            '"owned_by":"user@example.com",'
            '"run_by":null}'
        ),
        "record_type": "ORIGINAL",
        "ingestion_date": "2026-10-03",
        "billing_origin_product": "SQL",
        "product_features": (
            '{"is_photon":"true",'
            '"is_serverless":"true"}'
        ),
        "usage_type": "COMPUTE_TIME",
    }


def make_list_price_record() -> dict:
    """Create a representative list-price fixture."""
    return {
        "account_id": "account-test",
        "price_start_time": (
            "2024-09-23T00:00:00.000Z"
        ),
        "price_end_time": None,
        "sku_name": (
            "ENTERPRISE_DATABRICKS_STORAGE_US_WEST_CALIFORNIA"
        ),
        "cloud": "AWS",
        "currency_code": "USD",
        "usage_unit": "DSU",
        "pricing": (
            '{"default":"0.026000000000000000",'
            '"promotional":{"default":null},'
            '"effective_list":'
            '{"default":"0.026000000000000000"}}'
        ),
    }


def test_decimal_precision_is_preserved() -> None:
    result = normalize_billing_usage(
        source=make_usage_record(),
        collection_time=datetime.now(timezone.utc),
    )

    assert result.quantity == Decimal(
        "5.083760000000000000"
    )

    assert isinstance(
        result.quantity,
        Decimal,
    )


def test_timestamps_are_normalized_to_utc() -> None:
    result = normalize_billing_usage(
        source=make_usage_record(),
        collection_time=datetime.now(timezone.utc),
    )

    assert result.usage_start_time == datetime(
        2026,
        10,
        3,
        4,
        0,
        tzinfo=timezone.utc,
    )

    assert result.usage_end_time == datetime(
        2026,
        10,
        3,
        5,
        0,
        tzinfo=timezone.utc,
    )


def test_missing_cost_fields_are_not_invented() -> None:
    result = normalize_billing_usage(
        source=make_usage_record(),
        collection_time=datetime.now(timezone.utc),
    )

    assert result.list_price is None
    assert result.list_cost is None
    assert result.effective_price is None
    assert result.currency is None


def test_usage_metadata_is_mapped() -> None:
    result = normalize_billing_usage(
        source=make_usage_record(),
        collection_time=datetime.now(timezone.utc),
    )

    assert result.resource_id == "warehouse-test"
    assert result.resource_type == "sql_warehouse"
    assert result.resource_name is None
    assert result.user == "user@example.com"


def test_record_type_is_preserved() -> None:
    result = normalize_billing_usage(
        source=make_usage_record(),
        collection_time=datetime.now(timezone.utc),
    )

    assert result.additional_source_metadata is not None
    assert (
        result.additional_source_metadata["record_type"]
        == "ORIGINAL"
    )


def test_missing_usage_record_id_is_rejected() -> None:
    source = make_usage_record()
    source.pop("record_id")

    with pytest.raises(
        ValueError,
        match="record_id",
    ):
        normalize_billing_usage(
            source=source,
            collection_time=datetime.now(timezone.utc),
        )


def test_list_price_is_normalized() -> None:
    result = normalize_billing_list_price(
        source=make_list_price_record(),
        collection_time=datetime.now(timezone.utc),
    )

    assert (
        result.source_category
        == "billing_list_prices"
    )

    assert (
        result.sku
        == "ENTERPRISE_DATABRICKS_STORAGE_US_WEST_CALIFORNIA"
    )

    assert result.pricing_unit == "DSU"

    assert result.list_price == Decimal(
        "0.026000000000000000"
    )
    assert result.effective_price == Decimal(
        "0.026000000000000000"
    )

    assert result.currency == "USD"

    assert result.billing_start_time == datetime(
        2024,
        9,
        23,
        0,
        0,
        tzinfo=timezone.utc,
    )

    assert result.billing_end_time is None
    assert result.additional_source_metadata["open_ended_price"] is True


def test_list_price_does_not_invent_usage_or_cost() -> None:
    result = normalize_billing_list_price(
        source=make_list_price_record(),
        collection_time=datetime.now(timezone.utc),
    )

    assert result.quantity is None
    assert result.unit is None
    assert result.list_cost is None


def test_list_price_decimal_precision_is_preserved() -> None:
    result = normalize_billing_list_price(
        source=make_list_price_record(),
        collection_time=datetime.now(timezone.utc),
    )

    assert result.list_price == Decimal(
        "0.026000000000000000"
    )

    assert isinstance(
        result.list_price,
        Decimal,
    )


def test_missing_list_price_sku_is_rejected() -> None:
    source = make_list_price_record()
    source.pop("sku_name")

    with pytest.raises(
        ValueError,
        match="sku_name",
    ):
        normalize_billing_list_price(
            source=source,
            collection_time=datetime.now(timezone.utc),
        )


def test_malformed_source_fields_do_not_fail_normalization() -> None:
    source = make_usage_record()
    source["usage_start_time"] = "not-a-timestamp"
    source["usage_quantity"] = "not-a-number"
    source["usage_metadata"] = "{not json"

    result = normalize_billing_usage(
        source=source,
        collection_time=datetime.now(timezone.utc),
    )

    assert result.source_record_id == "record-test"
    assert result.usage_start_time is None
    assert result.quantity is None
    assert result.additional_source_metadata is not None
    assert result.additional_source_metadata["usage_metadata"] == {
        "_unparsed": "{not json",
    }