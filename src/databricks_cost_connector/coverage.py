from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .collectors import CollectionResult
from .models import CollectionStatus
from .normalizer import parse_timestamp


TIMESTAMP_FIELDS = (
    "usage_start_time",
    "usage_end_time",
    "price_start_time",
    "price_end_time",
    "start_time",
    "end_time",
    "event_time",
    "created_time",
    "updated_time",
    "update_time",
    "timestamp",
    "event_date",
    "usage_date",
)


def coverage_time_range(
    records: list[dict[str, Any]],
) -> tuple[datetime | None, datetime | None]:
    timestamps: list[datetime] = []
    for record in records:
        for field in TIMESTAMP_FIELDS:
            parsed = parse_timestamp(record.get(field))
            if parsed is not None:
                timestamps.append(parsed)
    if not timestamps:
        return None, None
    return min(timestamps), max(timestamps)


def status_explanation(result: CollectionResult) -> str:
    if result.status == CollectionStatus.COLLECTED:
        return (
            "Source query succeeded and returned one or more records."
        )
    if result.status == CollectionStatus.EMPTY:
        return (
            "Source table was accessible and the collection query "
            "succeeded, but it returned zero records at collection time."
        )
    if result.status == CollectionStatus.PERMISSION_DENIED:
        return (
            "The collection attempt was denied by the connected "
            "Databricks permissions."
        )
    if result.status == CollectionStatus.UNAVAILABLE_IN_ACCOUNT:
        return (
            "The source was not available in the connected "
            "Databricks account or workspace."
        )
    if result.status == CollectionStatus.UNSUPPORTED:
        return (
            "The source or capability is not supported as a Databricks "
            "system table in this connector/account."
        )
    if result.status == CollectionStatus.FAILED:
        return (
            "The connector attempted collection but the operation "
            "failed unexpectedly."
        )
    return "Collection completed with an unrecognized status."


def build_coverage_row(
    result: CollectionResult,
    *,
    discovered: bool | None = None,
    collection_started_at: datetime | None = None,
    normalized_record_count: int = 0,
    raw_output: str | None = None,
    normalized_output: str | None = None,
) -> dict[str, Any]:
    earliest, latest = coverage_time_range(result.records)
    completed = result.collected_at
    duration = None
    if collection_started_at is not None:
        duration = (completed - collection_started_at).total_seconds()

    return {
        "dataset": result.dataset.source,
        "source": result.dataset.source,
        "category": result.dataset.category,
        "assessment_category": result.dataset.assessment_category,
        "purpose": result.dataset.purpose,
        "status": result.status,
        "record_count": result.record_count,
        "earliest_source_timestamp": earliest,
        "latest_source_timestamp": latest,
        "required_capability": result.dataset.required_capability,
        "is_billed_cost_source": result.dataset.is_billed_cost_source,
        "discovered": discovered,
        "normalizable": result.dataset.normalizable,
        "raw_output": raw_output,
        "normalized_output": normalized_output,
        "error": result.error,
        "explanation": status_explanation(result),
        "collection_started_at": collection_started_at,
        "collection_completed_at": completed,
        "collection_duration_seconds": duration,
        "normalized_record_count": normalized_record_count,
    }


def synthetic_result(
    spec: Any,
    status: str,
    error: str | None = None,
) -> CollectionResult:
    return CollectionResult(
        dataset=spec,
        status=status,
        records=[],
        record_count=0,
        collected_at=datetime.now(timezone.utc),
        error=error,
    )
