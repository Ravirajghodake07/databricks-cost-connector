from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class CollectionStatus:
    COLLECTED = "COLLECTED"
    EMPTY = "EMPTY"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    UNAVAILABLE_IN_ACCOUNT = "UNAVAILABLE_IN_ACCOUNT"
    UNSUPPORTED = "UNSUPPORTED"
    FAILED = "FAILED"


class NormalizedCostRecord(BaseModel):
    """
    Canonical cost/usage representation.

    Fields that are not applicable to a particular source remain None.
    Source values are never invented.
    """

    model_config = ConfigDict(extra="allow")

    platform: str = "databricks"

    billing_account_id: str | None = None
    workspace_id: str | None = None

    source_category: str
    source_record_id: str

    resource_id: str | None = None
    resource_name: str | None = None
    resource_type: str | None = None

    workload_id: str | None = None
    workload_name: str | None = None
    workload_type: str | None = None

    service: str | None = None
    product: str | None = None
    sku: str | None = None

    usage_start_time: datetime | None = None
    usage_end_time: datetime | None = None

    billing_start_time: datetime | None = None
    billing_end_time: datetime | None = None

    quantity: Decimal | None = None
    unit: str | None = None
    pricing_quantity: Decimal | None = None
    pricing_unit: str | None = None

    list_price: Decimal | None = None
    list_cost: Decimal | None = None
    contracted_cost: Decimal | None = None
    effective_cost: Decimal | None = None
    billed_cost: Decimal | None = None
    effective_price: Decimal | None = None

    price_start_time: datetime | None = None
    price_end_time: datetime | None = None

    currency: str | None = None

    user: str | None = None
    service_principal: str | None = None

    tags: dict[str, Any] | None = None
    allocation_metadata: dict[str, Any] | None = None

    source_updated_at: datetime | None = None
    collection_time: datetime

    additional_source_metadata: dict[str, Any] | None = None
