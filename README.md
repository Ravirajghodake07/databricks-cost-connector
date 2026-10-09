# Databricks Cost Connector

Databricks Cost Connector Assessment: live connection, collection and normalization.

The connector authenticates to a real Databricks trial/development workspace from Python, discovers the cost-management data available to the account, collects every accessible dataset, preserves the raw records, normalizes applicable records to a common structure, and produces a coverage report. No database ingestion is performed (out of scope).

## Deliverables

| Required deliverable | Location |
|---|---|
| Python source code | `src/databricks_cost_connector/` |
| Pinned dependency file | `requirements.txt` |
| `.env.example` | `.env.example` |
| README with setup and execution instructions | this file |
| Coverage report | `evidence/coverage_report.json` (readable tables in `evidence/live_run.md`) |
| Redacted live execution evidence | `evidence/live_run.md` |
| Raw sample output | `evidence/raw_sample.jsonl` |
| Normalized sample output | `evidence/normalized_sample.jsonl` |
| Automated tests | `tests/` |
| Note on AI tools used | `docs/AI_USAGE.md` |

## Requirements

- Python 3.10+
- A Databricks trial or development workspace with Unity Catalog system tables
- A SQL warehouse (serverless is fine) and a personal access token

Dependencies are pinned in `requirements.txt`. The connector uses the official `databricks-sdk` (workspace authentication, warehouse lookup, Unity Catalog listing, Statement Execution API).

## Setup

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` with your own values. `.env` is gitignored; never commit it.

## Configuration (environment variables)

| Variable | Required | Description |
|---|---|---|
| `DATABRICKS_HOST` | yes | Workspace URL |
| `DATABRICKS_TOKEN` | yes | Personal access token |
| `DATABRICKS_WAREHOUSE_NAME` | no | SQL warehouse to use (default `Serverless Starter Warehouse`) |
| `DATABRICKS_START_TIME` | no | ISO-8601 start time; blank = unbounded |
| `DATABRICKS_END_TIME` | no | ISO-8601 end time; blank = unbounded |

Start and end time are applied to every source whose time column is known (billing usage, list prices, query history, warehouse events). Metadata tables are collected in full. Times without a zone are treated as UTC; others are converted to UTC. The start must be before the end.

## Run the connector

macOS / Linux:

```bash
export PYTHONPATH=src
python -m databricks_cost_connector.cli
```

Windows (PowerShell):

```powershell
$env:PYTHONPATH = "src"
python -m databricks_cost_connector.cli
```

Outputs are written to `output/` (gitignored):

| Path | Contents |
|---|---|
| `output/raw/<dataset>.jsonl` | Raw source records, unchanged |
| `output/normalized/<dataset>.jsonl` | Normalized records. Written only for datasets where normalization applies (billing usage, list prices, account prices, attributed usage). Other datasets are raw-only |
| `output/coverage_report.json` | One row per category investigated, including `normalized_record_count` and, when rows could not be normalized, `normalization_errors` (up to the first 20 details) |

Normalization errors are counted during processing. The coverage report includes the normalized record count and up to the first 20 normalization error details per dataset, so not every individual error is listed. Raw records are retained even when individual rows cannot be normalized.

To create the redacted submission evidence from a live run:

```bash
python scripts/create_submission_evidence.py
```

## Run the tests

Tests need no Databricks credentials and no network. They use small synthetic fixtures and mocks; they do not replace the live run.

```bash
python -m pytest
```

Covered: normalization, decimal precision, timestamp handling (UTC), empty results, malformed source records, permission and authentication failures, pagination, and time-window query building.

## How cost sources are discovered

1. Authenticate with the SDK using environment variables.
2. Locate the configured SQL warehouse.
3. List the schemas and tables of the Unity Catalog `system` catalog.
4. Match them against a registry of known cost-management datasets, and also investigate any other relevant table found.
5. Probe every registered dataset even if listing missed it, so an absent table is reported as `unavailable_in_account` instead of being dropped.
6. Collect each dataset independently. A failure in one dataset never stops the others.

## Collection behaviour

- Statements that are still running are polled until they finish.
- Every result chunk is retrieved. Failed chunk downloads are retried for up to 3 attempts total, with backoff. This retry policy does not apply to whole-query timeouts.
- Raw rows are written before normalization.
- Quantities, prices and costs are handled as `Decimal` and written as strings, never floats. Source identifiers are kept as given.
- Normalized timestamps are UTC.

## Coverage report

One row per category investigated, with: dataset name, purpose, status, record count, earliest and latest source timestamps, required permission or account capability, and an explanation when records were not collected (plus error text and per-dataset timing).

| Status | Meaning |
|---|---|
| `collected` | Query succeeded and returned records |
| `empty` | Table accessible, query succeeded, zero records |
| `permission_denied` | Access refused; required permission stated |
| `unavailable_in_account` | Table or feature does not exist in this account/workspace |
| `unsupported` | Source is not exposed through a queryable system table |
| `failed` | Collection was attempted and errored (for example a timeout) |

Note: the submitted JSON report prints these in upper case (`COLLECTED`, `EMPTY`, ...) with the same meanings.

Categories investigated: billing and usage; account and workspace consumption; cluster and compute; SQL warehouse; jobs and pipelines; serverless; storage; data transfer and network; SKU and pricing; list cost; resource and workload attribution; user and service-principal attribution; tags and allocation; budgets, alerts and cost controls; corrections and restatements; optimization and cost saving; contracts, commitments and discounts.

## Live run summary (from `evidence/live_run.md`)

- Datasets investigated: 36; records collected: 1,948
- Collected: 8 (billing usage 47, list prices 887, node types 653, warehouse events 60, warehouses 1, query history 271, workspaces 1, governed tags 28)
- Empty: 25; unavailable in account: 1; unsupported: 1 (account-console budgets); failed: 1 (pipeline events preview, request timeout)
- Permission denied: 0
- Collection window: 2026-10-06T17:31:07Z to 2026-10-06T17:43:16Z
- Billing usage source timestamps: 2026-10-03T00:00:00Z to 2026-10-05T14:00:00Z

The `failed` dataset (`system.lakeflow_pipeline_events_preview.pipeline_events`) timed out after about 298 seconds in the recorded run ("Request to delta sharing server failed ... likely caused by request timeout"). It was not retried or fixed, so it remains uncollected in the submitted evidence.

The counts above match `evidence/coverage_report.json` and `evidence/live_run.md`: 36 rows, 1,948 records, same statuses and timestamps.

Empty categories reflect this account's activity at collection time, not a connector fault. Credentials, tokens, email addresses and full account/workspace identifiers are redacted in all evidence.

## Normalized output

The canonical billing schema below describes normalized billing usage records. Other normalization-eligible datasets (list prices, account prices, attributed usage) are normalized according to their applicable source fields, so not every field is populated for every dataset. Datasets outside the normalization scope are preserved raw only.

A normalized billing usage record is mapped to: platform; billing account ID; workspace ID; source category; source record ID; resource/workload ID, name and type; service/product; SKU; usage start and end; billing period start and end; consumed quantity and unit; pricing quantity and unit; list unit price; list cost; contracted cost; effective cost; billed cost; currency; user or service-principal attribution; tags/allocation metadata; source update time; collection time; additional source metadata.

Rules:

- Fields that do not apply are `null`. Missing values are never invented.
- `record_type` (original, retraction, restatement) is preserved so corrections are not merged away.
- List cost is `quantity x unit price`, set only when exactly one price interval matches the usage by SKU, cloud, unit and time; otherwise it stays `null`.
- Contracted, effective and billed cost stay `null` unless the source provides them.
- Malformed rows are skipped and reported by row index (up to the first 20 per dataset); they do not fail the run.

## Limitations

- Account-console budgets are not available as a system table and are reported as `unsupported`.
- Very large or slow tables may time out and are reported as `failed`. This happened for the pipeline events preview table in the recorded run. Narrowing the time window may help; it was not tried.
- Normalization covers billing usage and price datasets; other collected datasets are preserved raw only.

## AI tools used

See `docs/AI_USAGE.md`.
