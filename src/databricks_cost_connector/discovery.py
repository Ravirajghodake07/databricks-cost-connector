from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from databricks.sdk import WorkspaceClient

from .models import CollectionStatus


SYSTEM_TABLE_CAPABILITY = "Unity Catalog system tables access"

# Time-filter kinds are applied only when the source timestamp semantics
# are understood. Unknown datasets remain unbounded snapshots.
TIME_FILTER_INTERVAL = "interval"
TIME_FILTER_POINT = "point"
TIME_FILTER_PRICE = "price"


@dataclass(frozen=True)
class DatasetSpec:
    category: str
    purpose: str
    source: str
    normalizable: bool
    required_capability: str
    assessment_category: str = "unspecified"
    is_billed_cost_source: bool = True
    time_filter: str | None = None
    start_column: str | None = None
    end_column: str | None = None


@dataclass
class PlannedDataset:
    spec: DatasetSpec
    discovered: bool
    status: str | None = None
    error: str | None = None


def _spec(
    category: str,
    purpose: str,
    source: str,
    assessment_category: str,
    *,
    normalizable: bool = True,
    is_billed_cost_source: bool = True,
    time_filter: str | None = None,
    start_column: str | None = None,
    end_column: str | None = None,
) -> DatasetSpec:
    return DatasetSpec(
        category=category,
        purpose=purpose,
        source=source,
        normalizable=normalizable,
        required_capability=SYSTEM_TABLE_CAPABILITY,
        assessment_category=assessment_category,
        is_billed_cost_source=is_billed_cost_source,
        time_filter=time_filter,
        start_column=start_column,
        end_column=end_column,
    )


# Registry of assessment-relevant datasets. This is a classification
# catalog, not the exclusive collection list. Discovered extra relevant
# tables are still investigated at runtime.
EXPECTED_DATASETS: tuple[DatasetSpec, ...] = (
    _spec(
        "billing_usage",
        "Billable usage records (primary billing source)",
        "system.billing.usage",
        "billing_usage",
        time_filter=TIME_FILTER_INTERVAL,
        start_column="usage_start_time",
        end_column="usage_end_time",
    ),
    _spec(
        "billing_list_prices",
        "Historical SKU list pricing, including open-ended current prices",
        "system.billing.list_prices",
        "sku_pricing",
        time_filter=TIME_FILTER_PRICE,
        start_column="price_start_time",
        end_column="price_end_time",
    ),
    _spec(
        "billing_account_prices",
        "Account-specific pricing, commitments, or contracted rates",
        "system.billing.account_prices",
        "contracts_commitments_discounts",
    ),
    _spec(
        "billing_attributed_usage",
        "Attributed billing usage for resource/workload allocation",
        "system.billing.attributed_usage",
        "resource_workload_attribution",
        time_filter=TIME_FILTER_INTERVAL,
        start_column="usage_start_time",
        end_column="usage_end_time",
    ),
    _spec(
        "compute_clusters",
        "Classic compute cluster configuration history",
        "system.compute.clusters",
        "cluster_compute",
        is_billed_cost_source=False,
    ),
    _spec(
        "compute_instance_events",
        "Classic compute instance lifecycle events",
        "system.compute.instance_events",
        "cluster_compute",
        is_billed_cost_source=False,
        time_filter=TIME_FILTER_POINT,
        start_column="event_time",
    ),
    _spec(
        "compute_instance_pools",
        "Instance pool configuration history",
        "system.compute.instance_pools",
        "cluster_compute",
        is_billed_cost_source=False,
    ),
    _spec(
        "compute_node_timeline",
        "Compute node utilization timeline",
        "system.compute.node_timeline",
        "cluster_compute",
        is_billed_cost_source=False,
    ),
    _spec(
        "compute_node_types",
        "Available compute node types",
        "system.compute.node_types",
        "cluster_compute",
        is_billed_cost_source=False,
    ),
    _spec(
        "compute_warehouse_events",
        "SQL warehouse lifecycle events",
        "system.compute.warehouse_events",
        "sql_warehouse",
        is_billed_cost_source=False,
        time_filter=TIME_FILTER_POINT,
        start_column="event_time",
    ),
    _spec(
        "compute_warehouses",
        "SQL warehouse configuration history, including serverless warehouses",
        "system.compute.warehouses",
        "sql_warehouse",
        is_billed_cost_source=False,
    ),
    _spec(
        "query_history",
        "SQL warehouse and serverless query workload history",
        "system.query.history",
        "sql_warehouse",
        is_billed_cost_source=False,
        time_filter=TIME_FILTER_INTERVAL,
        start_column="start_time",
        end_column="end_time",
    ),
    _spec(
        "storage_table_metrics",
        "Storage table metrics history",
        "system.storage.table_metrics_history",
        "storage",
        is_billed_cost_source=False,
    ),
    _spec(
        "storage_predictive_optimization",
        "Predictive optimization operations (cost-saving / storage optimization)",
        "system.storage.predictive_optimization_operations_history",
        "optimization_cost_saving",
        is_billed_cost_source=False,
    ),
    _spec(
        "storage_auto_upgrade",
        "Storage auto-upgrade operations",
        "system.storage.auto_upgrade_operations_history",
        "storage",
        is_billed_cost_source=False,
    ),
    _spec(
        "storage_table_auto_upgrade",
        "Unity Catalog managed table automatic upgrade operations",
        "system.storage.table_auto_upgrade_operations_history",
        "storage",
        is_billed_cost_source=False,
    ),
    _spec(
        "job_run_timeline",
        "Job execution timeline",
        "system.lakeflow.job_run_timeline",
        "jobs_pipelines",
        is_billed_cost_source=False,
    ),
    _spec(
        "job_task_run_timeline",
        "Job task execution timeline",
        "system.lakeflow.job_task_run_timeline",
        "jobs_pipelines",
        is_billed_cost_source=False,
    ),
    _spec(
        "job_tasks",
        "Job task metadata",
        "system.lakeflow.job_tasks",
        "jobs_pipelines",
        is_billed_cost_source=False,
    ),
    _spec(
        "jobs",
        "Job metadata",
        "system.lakeflow.jobs",
        "jobs_pipelines",
        is_billed_cost_source=False,
    ),
    _spec(
        "pipeline_update_timeline",
        "Pipeline update timeline",
        "system.lakeflow.pipeline_update_timeline",
        "jobs_pipelines",
        is_billed_cost_source=False,
    ),
    _spec(
        "pipelines",
        "Pipeline metadata",
        "system.lakeflow.pipelines",
        "jobs_pipelines",
        is_billed_cost_source=False,
    ),
    _spec(
        "zerobus_ingest",
        "ZeroBus ingestion activity",
        "system.lakeflow.zerobus_ingest",
        "jobs_pipelines",
        is_billed_cost_source=False,
    ),
    _spec(
        "zerobus_stream",
        "ZeroBus streaming activity",
        "system.lakeflow.zerobus_stream",
        "jobs_pipelines",
        is_billed_cost_source=False,
    ),
    _spec(
        "workspace_metadata",
        "Account workspace metadata for consumption attribution",
        "system.access.workspaces_latest",
        "account_workspace_consumption",
        is_billed_cost_source=False,
    ),
    _spec(
        "inbound_network",
        "Denied inbound network policy events (network/security, not billed usage)",
        "system.access.inbound_network",
        "data_transfer_network",
        is_billed_cost_source=False,
        time_filter=TIME_FILTER_POINT,
        start_column="event_time",
    ),
    _spec(
        "outbound_network",
        "Denied outbound network policy events (network/security, not billed usage)",
        "system.access.outbound_network",
        "data_transfer_network",
        is_billed_cost_source=False,
        time_filter=TIME_FILTER_POINT,
        start_column="event_time",
    ),
    _spec(
        "serving_endpoint_usage",
        "Model serving endpoint token usage",
        "system.serving.endpoint_usage",
        "serverless",
        is_billed_cost_source=False,
    ),
    _spec(
        "serving_served_entities",
        "Model serving endpoint entity metadata",
        "system.serving.served_entities",
        "serverless",
        is_billed_cost_source=False,
    ),
    _spec(
        "alert_configuration",
        "Alert configuration used for operational/cost-control notifications",
        "system.alert.alerts",
        "budgets_alerts_cost_controls",
        is_billed_cost_source=False,
    ),
    _spec(
        "alert_evaluation_history",
        "Alert evaluation history for cost-control monitoring",
        "system.alert.alert_evaluation_history",
        "budgets_alerts_cost_controls",
        is_billed_cost_source=False,
    ),
    _spec(
        "governed_tags",
        "Governed tag definitions used for allocation",
        "system.tags.governed_tags",
        "tags_allocation",
        is_billed_cost_source=False,
    ),
    _spec(
        "ai_gateway_usage",
        "AI Gateway model request usage",
        "system.ai_gateway.usage",
        "serverless",
        is_billed_cost_source=False,
    ),
    _spec(
        "ai_gateway_external_model_spend",
        "Estimated USD spend for AI Gateway external model requests",
        "system.ai_gateway.external_model_spend",
        "billing_usage",
        is_billed_cost_source=True,
    ),
)


UNSUPPORTED_CATEGORIES: tuple[DatasetSpec, ...] = (
    _spec(
        "databricks_budgets",
        "Databricks account-console budgets are not exposed as a dedicated system table",
        "databricks.account.budgets",
        "budgets_alerts_cost_controls",
        normalizable=False,
        is_billed_cost_source=False,
    ),
)


IRRELEVANT_TABLE_NAMES = frozenset(
    {
        "column_lineage",
        "table_lineage",
        "assistant_events",
        "clean_room_events",
        "audit",
    }
)

IRRELEVANT_SCHEMAS = frozenset(
    {
        "information_schema",
        "mlflow",
        "marketplace",
        "sharing",
        "replication",
        "data_classification",
        "data_quality_monitoring",
        "lakebase",
        "operational_data",
        "lineage",
        "__internal_logging",
    }
)

RELEVANT_SCHEMAS = frozenset(
    {
        "billing",
        "compute",
        "query",
        "storage",
        "lakeflow",
        "serving",
        "alert",
        "tags",
        "ai_gateway",
        "lakeflow_pipeline_events_preview",
    }
)

RELEVANT_NAME_TOKENS = (
    "usage",
    "price",
    "billing",
    "cost",
    "budget",
    "sku",
    "warehouse",
    "cluster",
    "job",
    "pipeline",
    "serverless",
    "commitment",
    "discount",
    "storage",
    "node",
    "instance",
    "serving",
    "alert",
    "tag",
    "spend",
    "network",
)

EXPECTED_BY_SOURCE = {item.source: item for item in EXPECTED_DATASETS}


def classify_status_message(message: str) -> str:
    text = message.lower()

    if (
        "401" in text
        or "invalid access token" in text
        or "unauthenticated" in text
        or "authentication" in text
    ):
        return CollectionStatus.FAILED

    if any(
        token in text
        for token in (
            "permission",
            "not authorized",
            "unauthorized",
            "forbidden",
            "access denied",
            "insufficient privileges",
            "privilege",
        )
    ):
        return CollectionStatus.PERMISSION_DENIED

    if any(
        token in text
        for token in (
            "not found",
            "does not exist",
            "unknown table",
            "table_or_view_not_found",
            "schema_not_found",
            "nocatalog",
        )
    ):
        return CollectionStatus.UNAVAILABLE_IN_ACCOUNT

    return CollectionStatus.FAILED


def classify_error_kind(message: str) -> str:
    status = classify_status_message(message)
    text = message.lower()
    if (
        "401" in text
        or "invalid access token" in text
        or "unauthenticated" in text
        or "authentication" in text
    ):
        return "authentication"
    if status == CollectionStatus.PERMISSION_DENIED:
        return "permission"
    if status == CollectionStatus.UNAVAILABLE_IN_ACCOUNT:
        return "unavailable"
    if status == CollectionStatus.UNSUPPORTED:
        return "unsupported"
    return "failed"


def classify_table(schema: str, table: str) -> bool:
    schema_l = schema.lower()
    table_l = table.lower()

    if schema_l in IRRELEVANT_SCHEMAS:
        return False

    if table_l in IRRELEVANT_TABLE_NAMES:
        return False

    if schema_l in RELEVANT_SCHEMAS:
        return True

    if schema_l == "access" and (
        table_l == "workspaces_latest" or "network" in table_l
    ):
        return True

    return any(token in table_l or token in schema_l for token in RELEVANT_NAME_TOKENS)


def spec_for_discovered_table(full_name: str) -> DatasetSpec:
    known = EXPECTED_BY_SOURCE.get(full_name)
    if known is not None:
        return known

    parts = full_name.split(".")
    schema = parts[1] if len(parts) >= 3 else (parts[0] if parts else "unknown")
    table = parts[-1]

    assessment = "discovered_relevant"
    billed = schema == "billing" or "price" in table or "usage" in table or "spend" in table
    if schema == "compute":
        assessment = "cluster_compute" if "warehouse" not in table else "sql_warehouse"
        billed = False
    elif schema == "lakeflow" or "pipeline" in schema:
        assessment = "jobs_pipelines"
        billed = False
    elif schema == "storage":
        assessment = (
            "optimization_cost_saving" if "optim" in table else "storage"
        )
        billed = False
    elif schema in {"serving", "ai_gateway"}:
        assessment = "serverless"
        billed = "spend" in table or "usage" in table
    elif schema == "alert":
        assessment = "budgets_alerts_cost_controls"
        billed = False
    elif schema == "tags":
        assessment = "tags_allocation"
        billed = False
    elif "network" in table:
        assessment = "data_transfer_network"
        billed = False
    elif schema == "billing":
        assessment = "billing_usage"

    return DatasetSpec(
        category=f"{schema}_{table}",
        purpose=f"Discovered relevant {schema} table `{full_name}`",
        source=full_name,
        normalizable=billed,
        required_capability=SYSTEM_TABLE_CAPABILITY,
        assessment_category=assessment,
        is_billed_cost_source=billed,
    )


def _full_name(schema: str, table: str) -> str:
    return f"system.{schema}.{table}"



def list_system_tables(client: WorkspaceClient) -> tuple[set[str], str | None]:
    """Discover system tables via Unity Catalog APIs.

    Returns discovered table names and an optional discovery error.
    Individual schema failures are reported rather than silently ignored.
    """
    discovered: set[str] = set()
    discovery_errors: list[str] = []

    try:
        schemas = list(client.schemas.list(catalog_name="system"))
    except Exception as exc:
        return set(), str(exc)

    for schema in schemas:
        schema_name = getattr(schema, "name", None)
        if not schema_name or schema_name.lower() in IRRELEVANT_SCHEMAS:
            continue

        try:
            tables = list(
                client.tables.list(
                    catalog_name="system",
                    schema_name=schema_name,
                )
            )
        except Exception as exc:
            discovery_errors.append(
                f"Schema '{schema_name}': {exc}"
            )
            continue

        for table in tables:
            table_name = getattr(table, "name", None)
            if not table_name:
                continue
            discovered.add(_full_name(schema_name, table_name))

    if discovery_errors:
        return discovered, (
            "Some system schemas could not be discovered: "
            + "; ".join(discovery_errors)
        )

    return discovered, None



def plan_collection(
    discovered: Iterable[str],
    discovery_error: str | None = None,
) -> list[PlannedDataset]:
    discovered_set = {item.lower() for item in discovered}
    planned: list[PlannedDataset] = []
    seen: set[str] = set()

    for spec in EXPECTED_DATASETS:
        key = spec.source.lower()
        seen.add(key)

        planned.append(
            PlannedDataset(
                spec=spec,
                discovered=key in discovered_set,
            )
        )

    if not discovered_set:
        for spec in UNSUPPORTED_CATEGORIES:
            planned.append(
                PlannedDataset(
                    spec=spec,
                    discovered=False,
                    status=CollectionStatus.UNSUPPORTED,
                    error=spec.purpose,
                )
            )
        return planned

    for full_name in sorted(discovered_set):
        if full_name in seen:
            continue
        parts = full_name.split(".")
        if len(parts) != 3:
            continue
        _, schema, table = parts
        if not classify_table(schema, table):
            continue
        spec = spec_for_discovered_table(full_name)
        planned.append(PlannedDataset(spec=spec, discovered=True))
        seen.add(full_name)

    budget_found = any(
        "budget" in item.spec.source.lower()
        for item in planned
        if item.status is None and item.spec.source.startswith("system.")
    )

    for spec in UNSUPPORTED_CATEGORIES:
        if spec.source.endswith(".budgets") and budget_found:
            continue
        planned.append(
            PlannedDataset(
                spec=spec,
                discovered=False,
                status=CollectionStatus.UNSUPPORTED,
                error=spec.purpose,
            )
        )

    return planned


def with_discovery_failure(
    planned: list[PlannedDataset],
    error: str,
) -> list[PlannedDataset]:
    status = classify_status_message(error)
    extra = DatasetSpec(
        category="system_catalog_discovery",
        purpose="Dynamic discovery of Unity Catalog system tables",
        source="system.information_schema.tables",
        normalizable=False,
        required_capability=SYSTEM_TABLE_CAPABILITY,
        assessment_category="discovery",
        is_billed_cost_source=False,
    )
    return [
        PlannedDataset(
            spec=extra,
            discovered=False,
            status=status,
            error=error,
        ),
        *planned,
    ]


def discovery_summary(planned: list[PlannedDataset]) -> dict[str, Any]:
    return {
        "investigated_count": len(planned),
        "discovered_count": sum(1 for item in planned if item.discovered),
        "preclassified_unavailable": sum(
            1
            for item in planned
            if item.status == CollectionStatus.UNAVAILABLE_IN_ACCOUNT
        ),
        "preclassified_unsupported": sum(
            1
            for item in planned
            if item.status == CollectionStatus.UNSUPPORTED
        ),
    }
