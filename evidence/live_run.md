# Redacted Live Execution Evidence

This document records a live execution of the Databricks cost connector against the assessment development/trial workspace.

Sensitive credentials, email addresses, and complete account/workspace identifiers are intentionally excluded.

## Execution summary

- Datasets investigated: **36**
- Total records collected: **1,948**
- Collected datasets: **8**
- Empty datasets: **25**
- Permission denied: **0**
- Unavailable in account: **1**
- Unsupported: **1**
- Failed: **1**
- Collection started: **2026-10-06T17:31:07.255584+00:00**
- Collection completed: **2026-10-06T17:43:16.833332+00:00**

## Successful collections

| Dataset | Records | Earliest source timestamp | Latest source timestamp |
|---|---:|---|---|
| `system.billing.usage` | 47 | 2026-10-03T00:00:00+00:00 | 2026-10-05T14:00:00+00:00 |
| `system.billing.list_prices` | 887 | 2013-01-01T00:00:00+00:00 | 2026-08-21T00:00:00+00:00 |
| `system.compute.node_types` | 653 | N/A | N/A |
| `system.compute.warehouse_events` | 60 | 2026-10-03T04:25:15.989000+00:00 | 2026-10-06T16:39:11.339000+00:00 |
| `system.compute.warehouses` | 1 | N/A | N/A |
| `system.query.history` | 271 | 2026-10-03T04:25:16.785000+00:00 | 2026-10-06T16:28:33.627000+00:00 |
| `system.access.workspaces_latest` | 1 | N/A | N/A |
| `system.tags.governed_tags` | 28 | N/A | N/A |

## Non-collected categories

| Dataset | Status | Records | Explanation |
|---|---|---:|---|
| `system.billing.account_prices` | `EMPTY` | 0 | Source table was accessible and the collection query succeeded, but it returned zero records at collection time. |
| `system.billing.attributed_usage` | `EMPTY` | 0 | Source table was accessible and the collection query succeeded, but it returned zero records at collection time. |
| `system.compute.clusters` | `EMPTY` | 0 | Source table was accessible and the collection query succeeded, but it returned zero records at collection time. |
| `system.compute.instance_events` | `EMPTY` | 0 | Source table was accessible and the collection query succeeded, but it returned zero records at collection time. |
| `system.compute.instance_pools` | `EMPTY` | 0 | Source table was accessible and the collection query succeeded, but it returned zero records at collection time. |
| `system.compute.node_timeline` | `EMPTY` | 0 | Source table was accessible and the collection query succeeded, but it returned zero records at collection time. |
| `system.storage.table_metrics_history` | `EMPTY` | 0 | Source table was accessible and the collection query succeeded, but it returned zero records at collection time. |
| `system.storage.predictive_optimization_operations_history` | `EMPTY` | 0 | Source table was accessible and the collection query succeeded, but it returned zero records at collection time. |
| `system.storage.auto_upgrade_operations_history` | `EMPTY` | 0 | Source table was accessible and the collection query succeeded, but it returned zero records at collection time. |
| `system.storage.table_auto_upgrade_operations_history` | `UNAVAILABLE_IN_ACCOUNT` | 0 | The source was not available in the connected Databricks account or workspace. |
| `system.lakeflow.job_run_timeline` | `EMPTY` | 0 | Source table was accessible and the collection query succeeded, but it returned zero records at collection time. |
| `system.lakeflow.job_task_run_timeline` | `EMPTY` | 0 | Source table was accessible and the collection query succeeded, but it returned zero records at collection time. |
| `system.lakeflow.job_tasks` | `EMPTY` | 0 | Source table was accessible and the collection query succeeded, but it returned zero records at collection time. |
| `system.lakeflow.jobs` | `EMPTY` | 0 | Source table was accessible and the collection query succeeded, but it returned zero records at collection time. |
| `system.lakeflow.pipeline_update_timeline` | `EMPTY` | 0 | Source table was accessible and the collection query succeeded, but it returned zero records at collection time. |
| `system.lakeflow.pipelines` | `EMPTY` | 0 | Source table was accessible and the collection query succeeded, but it returned zero records at collection time. |
| `system.lakeflow.zerobus_ingest` | `EMPTY` | 0 | Source table was accessible and the collection query succeeded, but it returned zero records at collection time. |
| `system.lakeflow.zerobus_stream` | `EMPTY` | 0 | Source table was accessible and the collection query succeeded, but it returned zero records at collection time. |
| `system.access.inbound_network` | `EMPTY` | 0 | Source table was accessible and the collection query succeeded, but it returned zero records at collection time. |
| `system.access.outbound_network` | `EMPTY` | 0 | Source table was accessible and the collection query succeeded, but it returned zero records at collection time. |
| `system.serving.endpoint_usage` | `EMPTY` | 0 | Source table was accessible and the collection query succeeded, but it returned zero records at collection time. |
| `system.serving.served_entities` | `EMPTY` | 0 | Source table was accessible and the collection query succeeded, but it returned zero records at collection time. |
| `system.alert.alerts` | `EMPTY` | 0 | Source table was accessible and the collection query succeeded, but it returned zero records at collection time. |
| `system.alert.alert_evaluation_history` | `EMPTY` | 0 | Source table was accessible and the collection query succeeded, but it returned zero records at collection time. |
| `system.ai_gateway.usage` | `EMPTY` | 0 | Source table was accessible and the collection query succeeded, but it returned zero records at collection time. |
| `system.ai_gateway.external_model_spend` | `EMPTY` | 0 | Source table was accessible and the collection query succeeded, but it returned zero records at collection time. |
| `system.lakeflow_pipeline_events_preview.pipeline_events` | `FAILED` | 0 | The connector attempted collection but the operation failed unexpectedly. |
| `databricks.account.budgets` | `UNSUPPORTED` | 0 | The source or capability is not supported as a Databricks system table in this connector/account. |

## Authentication and workspace discovery

The connector successfully authenticated using environment-based Databricks credentials and successfully discovered and used the configured Serverless Starter Warehouse.

Credentials, tokens, email addresses, and complete account/workspace identifiers are intentionally not included in this evidence.

## Collection behavior demonstrated

- Uses the Databricks Python SDK Statement Execution API.
- Executes collection independently for each registered dataset.
- Polls statements that remain in a running state.
- Retrieves additional result chunks when a statement result contains multiple chunks.
- Preserves raw records before normalization.
- Produces normalized records for applicable billing datasets.
- Distinguishes collected, empty, permission, unavailable, unsupported, and failed states.

## Evidence files

- `coverage_report.json` - redacted machine-readable coverage report.
- `raw_sample.jsonl` - redacted sample of raw source records.
- `normalized_sample.jsonl` - redacted sample of normalized records.
