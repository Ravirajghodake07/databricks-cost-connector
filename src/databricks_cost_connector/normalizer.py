from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from .models import NormalizedCostRecord


def parse_json_object(value: Any) -> dict[str, Any] | None:
    """Parse a JSON object stored as a string or return an existing mapping."""
    if value is None:
        return None

    if isinstance(value, dict):
        return value

    if isinstance(value, str):
        if not value.strip():
            return None
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {"_unparsed": value}
        return parsed if isinstance(parsed, dict) else {"_unparsed": value}

    return None


def parse_decimal(value: Any) -> Decimal | None:
    """Convert a source numeric value to Decimal without float conversion."""
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def parse_timestamp(value: Any) -> datetime | None:
    """Parse a source timestamp and normalize it to UTC."""
    if value is None:
        return None

    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def require_record_id(
    source: dict[str, Any],
    field_name: str = "record_id",
) -> str:
    value = source.get(field_name)
    if value is None or not str(value).strip():
        raise ValueError(f"Source record is missing required {field_name}.")
    return str(value)


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _resource_from_usage_metadata(
    usage_metadata: dict[str, Any],
) -> tuple[str | None, str | None, str | None]:
    mapping = (
        ("cluster_id", None, "cluster"),
        ("warehouse_id", None, "sql_warehouse"),
        ("endpoint_id", "endpoint_name", "serving_endpoint"),
        ("dlt_pipeline_id", None, "pipeline"),
        ("instance_pool_id", None, "instance_pool"),
        ("notebook_id", None, "notebook"),
    )
    for id_key, name_key, resource_type in mapping:
        resource_id = _as_str(usage_metadata.get(id_key))
        if resource_id:
            resource_name = _as_str(usage_metadata.get(name_key)) if name_key else None
            return resource_id, resource_name, resource_type
    return None, None, None


def _workload_from_usage_metadata(
    usage_metadata: dict[str, Any],
) -> tuple[str | None, str | None, str | None]:
    job_run_id = _as_str(usage_metadata.get("job_run_id"))
    job_id = _as_str(usage_metadata.get("job_id"))
    job_name = _as_str(usage_metadata.get("job_name"))
    if job_run_id or job_id or job_name:
        return job_run_id or job_id, job_name, "job"
    pipeline_id = _as_str(usage_metadata.get("dlt_pipeline_id"))
    if pipeline_id:
        return pipeline_id, None, "pipeline"
    return None, None, None


def normalize_billing_usage(
    source: dict[str, Any],
    collection_time: datetime,
) -> NormalizedCostRecord:
    """Normalize one system.billing.usage record without inventing cost."""
    record_id = require_record_id(source)

    usage_metadata = parse_json_object(source.get("usage_metadata")) or {}
    identity_metadata = parse_json_object(source.get("identity_metadata")) or {}
    product_features = parse_json_object(source.get("product_features"))
    custom_tags = parse_json_object(source.get("custom_tags"))

    resource_id, resource_name, resource_type = _resource_from_usage_metadata(
        usage_metadata
    )
    workload_id, workload_name, workload_type = _workload_from_usage_metadata(
        usage_metadata
    )

    parsed_collection_time = parse_timestamp(collection_time)
    if parsed_collection_time is None:
        raise ValueError("collection_time must be a valid timestamp.")

    owned_by = identity_metadata.get("owned_by") or identity_metadata.get("created_by")

    explicit_service_principal = identity_metadata.get("service_principal")
    service_principal = (
        _as_str(explicit_service_principal)
        if explicit_service_principal
        else None
    )

    return NormalizedCostRecord(
        platform="databricks",
        billing_account_id=_as_str(source.get("account_id")),
        workspace_id=_as_str(source.get("workspace_id")),
        source_category="billing_usage",
        source_record_id=record_id,
        resource_id=resource_id,
        resource_name=resource_name,
        resource_type=resource_type,
        workload_id=workload_id,
        workload_name=workload_name,
        workload_type=workload_type,
        service=_as_str(source.get("billing_origin_product")),
        product=_as_str(source.get("billing_origin_product")),
        sku=_as_str(source.get("sku_name")),
        usage_start_time=parse_timestamp(source.get("usage_start_time")),
        usage_end_time=parse_timestamp(source.get("usage_end_time")),
        billing_start_time=None,
        billing_end_time=None,
        quantity=parse_decimal(source.get("usage_quantity")),
        unit=_as_str(source.get("usage_unit")),
        pricing_quantity=parse_decimal(source.get("usage_quantity")),
        pricing_unit=_as_str(source.get("usage_unit")),
        list_price=None,
        effective_price=None,
        list_cost=None,
        currency=None,
        user=_as_str(owned_by),
        service_principal=_as_str(service_principal),
        tags=custom_tags if custom_tags and "_unparsed" not in custom_tags else (
            None if not custom_tags else custom_tags
        ),
        allocation_metadata={
            "cloud": source.get("cloud"),
            "usage_date": source.get("usage_date"),
            "usage_type": source.get("usage_type"),
        },
        source_updated_at=parse_timestamp(
            source.get("ingestion_date") or source.get("usage_date")
        ),
        collection_time=parsed_collection_time,
        additional_source_metadata={
            "record_type": source.get("record_type"),
            "ingestion_date": source.get("ingestion_date"),
            "node_type": usage_metadata.get("node_type"),
            "product_features": product_features,
            "identity_metadata": identity_metadata,
            "usage_metadata": usage_metadata,
            "custom_tags_raw": source.get("custom_tags")
            if isinstance(custom_tags, dict) and "_unparsed" in custom_tags
            else None,
        },
    )


def _extract_list_price_values(
    source: dict[str, Any],
) -> tuple[Decimal | None, Decimal | None, dict[str, Any], dict[str, Any], dict[str, Any]]:
    pricing = parse_json_object(source.get("pricing")) or {}
    effective_list = parse_json_object(pricing.get("effective_list")) or {}
    promotional = parse_json_object(pricing.get("promotional")) or {}

    effective_default = effective_list.get("default")
    if effective_default is None:
        effective_default = pricing.get("default")

    list_default = pricing.get("default")
    return (
        parse_decimal(list_default),
        parse_decimal(effective_default),
        pricing,
        promotional,
        effective_list,
    )


def normalize_billing_list_price(
    source: dict[str, Any],
    collection_time: datetime,
) -> NormalizedCostRecord:
    """
    Normalize one system.billing.list_prices record.

    Databricks list_prices does not provide a record_id field in the observed
    source schema. A deterministic composite source key is therefore used as
    the canonical connector identifier, while original pricing fields are
    preserved in additional_source_metadata.

    No consumed quantity or total cost is invented from a price-only record.
    Open-ended current prices keep a null billing_end_time.
    """
    sku_name = source.get("sku_name")
    if sku_name is None or not str(sku_name).strip():
        raise ValueError("List price record is missing required sku_name.")

    price_start = parse_timestamp(source.get("price_start_time"))
    price_end = parse_timestamp(source.get("price_end_time"))
    cloud = source.get("cloud")
    usage_unit = source.get("usage_unit")

    source_record_id = "|".join(
        str(value or "")
        for value in (
            sku_name,
            source.get("price_start_time"),
            source.get("price_end_time"),
            cloud,
            usage_unit,
        )
    )

    list_price, effective_price, pricing, promotional, effective_list = (
        _extract_list_price_values(source)
    )

    parsed_collection_time = parse_timestamp(collection_time)
    if parsed_collection_time is None:
        raise ValueError("collection_time must be a valid timestamp.")

    return NormalizedCostRecord(
        platform="databricks",
        billing_account_id=_as_str(source.get("account_id")),
        workspace_id=None,
        source_category="billing_list_prices",
        source_record_id=source_record_id,
        resource_id=None,
        resource_name=None,
        resource_type=None,
        workload_id=None,
        workload_name=None,
        workload_type=None,
        service=None,
        product=None,
        sku=str(sku_name),
        usage_start_time=None,
        usage_end_time=None,
        billing_start_time=price_start,
        billing_end_time=price_end,
        quantity=None,
        unit=None,
        pricing_quantity=None,
        pricing_unit=_as_str(usage_unit),
        list_price=list_price,
        list_cost=None,
        contracted_cost=None,
        effective_cost=None,
        billed_cost=None,
        effective_price=effective_price,
        price_start_time=price_start,
        price_end_time=price_end,
        currency=_as_str(source.get("currency_code")),
        user=None,
        service_principal=None,
        tags=None,
        allocation_metadata={"cloud": cloud},
        source_updated_at=None,
        collection_time=parsed_collection_time,
        additional_source_metadata={
            "price_start_time": source.get("price_start_time"),
            "price_end_time": source.get("price_end_time"),
            "usage_unit": usage_unit,
            "pricing": pricing,
            "promotional": promotional,
            "effective_list": effective_list,
            "open_ended_price": price_end is None,
        },
    )


def apply_list_cost(
    usage: NormalizedCostRecord,
    price_records: list[NormalizedCostRecord],
) -> NormalizedCostRecord:
    """
    Deterministically attach list price/cost when a unique matching SKU
    price interval exists. No value is invented when a match is missing.
    """
    if usage.list_cost is not None:
        return usage
    if usage.sku is None or usage.quantity is None:
        return usage

    usage_time = usage.usage_end_time or usage.usage_start_time
    cloud = None
    if usage.allocation_metadata:
        cloud = usage.allocation_metadata.get("cloud")

    matches: list[NormalizedCostRecord] = []
    for price in price_records:
        if price.sku != usage.sku:
            continue
        price_cloud = None
        if price.allocation_metadata:
            price_cloud = price.allocation_metadata.get("cloud")
        if cloud and price_cloud and cloud != price_cloud:
            continue
        price_unit = None
        if price.additional_source_metadata:
            price_unit = price.additional_source_metadata.get("usage_unit")
        if usage.unit and price_unit and usage.unit != price_unit:
            continue
        if usage_time is None:
            continue
        if price.billing_start_time and usage_time < price.billing_start_time:
            continue
        if price.billing_end_time is not None and not (
            usage_time < price.billing_end_time
        ):
            continue
        matches.append(price)

    if not matches:
        return usage

    matches.sort(
        key=lambda item: item.billing_start_time or datetime.min.replace(
            tzinfo=timezone.utc
        ),
        reverse=True,
    )
    chosen = matches[0]
    unit_price = chosen.effective_price or chosen.list_price
    if unit_price is None:
        return usage

    usage.list_price = chosen.list_price
    usage.effective_price = chosen.effective_price
    usage.list_cost = usage.quantity * unit_price
    usage.currency = usage.currency or chosen.currency
    return usage


def normalize_records(
    source_name: str,
    records: list[dict[str, Any]],
    collection_time: datetime,
) -> tuple[list[NormalizedCostRecord], list[str]]:
    """Normalize applicable records; skip malformed rows without failing the run."""
    errors: list[str] = []
    normalized: list[NormalizedCostRecord] = []

    if source_name == "system.billing.usage":
        normalizer = normalize_billing_usage
    elif source_name in {
        "system.billing.list_prices",
        "system.billing.account_prices",
    }:
        normalizer = normalize_billing_list_price
    elif source_name == "system.billing.attributed_usage":
        normalizer = normalize_billing_usage
    else:
        return [], errors

    for index, record in enumerate(records):
        try:
            normalized.append(normalizer(record, collection_time))
        except Exception as exc:
            errors.append(f"row {index}: {exc}")

    return normalized, errors
