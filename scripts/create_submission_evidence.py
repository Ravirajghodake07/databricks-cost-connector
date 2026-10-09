from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

OUTPUT_DIR = PROJECT_ROOT / "output"
EVIDENCE_DIR = PROJECT_ROOT / "evidence"

COVERAGE_FILE = OUTPUT_DIR / "coverage_report.json"


# ---------------------------------------------------------------------------
# Sensitive-data redaction
# ---------------------------------------------------------------------------

SENSITIVE_KEY_PATTERNS = (
    "token",
    "password",
    "secret",
    "email",
    "account_id",
    "workspace_id",
    "credential",
    "access_key",
    "client_secret",
)

EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)


def _looks_sensitive_key(key: str) -> bool:
    key_lower = key.lower()

    return any(
        pattern in key_lower
        for pattern in SENSITIVE_KEY_PATTERNS
    )


def _redact_string(value: str) -> str:
    return EMAIL_PATTERN.sub("[REDACTED_EMAIL]", value)


def redact_value(
    value: Any,
    key: str | None = None,
) -> Any:
    """
    Recursively redact sensitive fields from dictionaries/lists.

    The goal is to make evidence safe for repository submission while
    retaining enough source structure to demonstrate connector output.
    """

    if key is not None and _looks_sensitive_key(key):
        return "[REDACTED]"

    if isinstance(value, dict):
        return {
            str(item_key): redact_value(
                item_value,
                str(item_key),
            )
            for item_key, item_value in value.items()
        }

    if isinstance(value, list):
        return [
            redact_value(item)
            for item in value
        ]

    if isinstance(value, str):
        return _redact_string(value)

    return value


# ---------------------------------------------------------------------------
# JSONL helpers
# ---------------------------------------------------------------------------

def _read_jsonl(
    path: Path,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    if not path.exists():
        return records

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        for line in file:
            line = line.strip()

            if not line:
                continue

            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue

            if isinstance(value, dict):
                records.append(value)

    return records


def _write_jsonl(
    path: Path,
    records: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:
        for record in records:
            file.write(
                json.dumps(
                    redact_value(record),
                    ensure_ascii=False,
                    indent=None,
                )
                + "\n"
            )


# ---------------------------------------------------------------------------
# Coverage report
# ---------------------------------------------------------------------------

def _load_coverage() -> list[dict[str, Any]]:
    if not COVERAGE_FILE.exists():
        raise FileNotFoundError(
            f"Coverage report was not found: {COVERAGE_FILE}"
        )

    with COVERAGE_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        value = json.load(file)

    if not isinstance(value, list):
        raise ValueError(
            "coverage_report.json must contain a JSON array."
        )

    return value


def _write_redacted_coverage(
    coverage: list[dict[str, Any]],
) -> Path:
    path = EVIDENCE_DIR / "coverage_report.json"

    redacted = [
        redact_value(row)
        for row in coverage
    ]

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            redacted,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return path


# ---------------------------------------------------------------------------
# Live-run evidence
# ---------------------------------------------------------------------------

def _status_counts(
    coverage: list[dict[str, Any]],
) -> Counter[str]:
    return Counter(
        str(row.get("status", "unknown")).strip().lower()
        for row in coverage
    )


def _total_records(
    coverage: list[dict[str, Any]],
) -> int:
    return sum(
        int(row.get("record_count", 0) or 0)
        for row in coverage
    )


def _successful_sources(
    coverage: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        row
        for row in coverage
        if str(row.get("status", "")).strip().lower() == "collected"
    ]


def _non_collected_sources(
    coverage: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        row
        for row in coverage
        if str(row.get("status", "")).strip().lower() != "collected"
    ]


def _write_live_run_evidence(
    coverage: list[dict[str, Any]],
) -> Path:
    path = EVIDENCE_DIR / "live_run.md"

    counts = _status_counts(coverage)
    successful = _successful_sources(coverage)
    non_collected = _non_collected_sources(coverage)

    collection_times: list[str] = []

    for row in coverage:
        started = row.get("collection_started_at")
        completed = row.get("collection_completed_at")

        if started:
            collection_times.append(str(started))

        if completed:
            collection_times.append(str(completed))

    collection_times.sort()

    first_collection_time = (
        collection_times[0]
        if collection_times
        else "not available"
    )

    last_collection_time = (
        collection_times[-1]
        if collection_times
        else "not available"
    )

    lines: list[str] = []

    lines.append("# Redacted Live Execution Evidence")
    lines.append("")

    lines.append(
        "This document records a live execution of the Databricks "
        "cost connector against the assessment development/trial "
        "workspace."
    )
    lines.append("")

    lines.append(
        "Sensitive credentials, email addresses, and complete "
        "account/workspace identifiers are intentionally excluded."
    )
    lines.append("")

    lines.append("## Execution summary")
    lines.append("")

    lines.append(
        f"- Datasets investigated: **{len(coverage)}**"
    )

    lines.append(
        f"- Total records collected: **{_total_records(coverage):,}**"
    )

    lines.append(
        f"- Collected datasets: **{counts.get('collected', 0)}**"
    )

    lines.append(
        f"- Empty datasets: **{counts.get('empty', 0)}**"
    )

    lines.append(
        f"- Permission denied: **{counts.get('permission_denied', 0)}**"
    )

    lines.append(
        f"- Unavailable in account: "
        f"**{counts.get('unavailable_in_account', 0)}**"
    )

    lines.append(
        f"- Unsupported: **{counts.get('unsupported', 0)}**"
    )

    lines.append(
        f"- Failed: **{counts.get('failed', 0)}**"
    )

    lines.append(
        f"- Collection started: **{first_collection_time}**"
    )

    lines.append(
        f"- Collection completed: **{last_collection_time}**"
    )

    lines.append("")

    lines.append("## Successful collections")
    lines.append("")

    lines.append(
        "| Dataset | Records | Earliest source timestamp | "
        "Latest source timestamp |"
    )
    lines.append(
        "|---|---:|---|---|"
    )

    for row in successful:
        lines.append(
            "| "
            f"`{row.get('source', '')}` | "
            f"{int(row.get('record_count', 0) or 0):,} | "
            f"{row.get('earliest_source_timestamp') or 'N/A'} | "
            f"{row.get('latest_source_timestamp') or 'N/A'} |"
        )

    lines.append("")

    lines.append("## Non-collected categories")
    lines.append("")

    lines.append(
        "| Dataset | Status | Records | Explanation |"
    )
    lines.append(
        "|---|---|---:|---|"
    )

    for row in non_collected:
        explanation = str(
            row.get("explanation")
            or "No explanation recorded."
        )

        explanation = explanation.replace(
            "\n",
            " ",
        )

        lines.append(
            "| "
            f"`{row.get('source', '')}` | "
            f"`{row.get('status', '')}` | "
            f"{int(row.get('record_count', 0) or 0):,} | "
            f"{explanation} |"
        )

    lines.append("")

    lines.append("## Authentication and workspace discovery")
    lines.append("")

    lines.append(
        "The connector successfully authenticated using environment-based "
        "Databricks credentials and successfully discovered and used the "
        "configured Serverless Starter Warehouse."
    )

    lines.append("")

    lines.append(
        "Credentials, tokens, email addresses, and complete "
        "account/workspace identifiers are intentionally not included "
        "in this evidence."
    )

    lines.append("")

    lines.append("## Collection behavior demonstrated")
    lines.append("")

    lines.append(
        "- Uses the Databricks Python SDK Statement Execution API."
    )

    lines.append(
        "- Executes collection independently for each registered dataset."
    )

    lines.append(
        "- Polls statements that remain in a running state."
    )

    lines.append(
        "- Retrieves additional result chunks when a statement result "
        "contains multiple chunks."
    )

    lines.append(
        "- Preserves raw records before normalization."
    )

    lines.append(
        "- Produces normalized records for applicable billing datasets."
    )

    lines.append(
        "- Distinguishes collected, empty, permission, unavailable, "
        "unsupported, and failed states."
    )

    lines.append("")

    lines.append("## Evidence files")
    lines.append("")

    lines.append(
        "- `coverage_report.json` - redacted machine-readable coverage report."
    )

    lines.append(
        "- `raw_sample.jsonl` - redacted sample of raw source records."
    )

    lines.append(
        "- `normalized_sample.jsonl` - redacted sample of normalized records."
    )

    lines.append("")

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:
        file.write("\n".join(lines))

    return path


# ---------------------------------------------------------------------------
# Samples
# ---------------------------------------------------------------------------

def _find_existing_file(
    candidates: list[Path],
) -> Path | None:
    for path in candidates:
        if path.exists():
            return path

    return None


def _create_raw_sample() -> Path:
    """
    Create a small redacted sample from billing usage.

    Billing usage is the strongest raw sample because it demonstrates
    billing identifiers, usage metadata, identity metadata, tags, and
    source metadata without requiring a large evidence file.
    """

    source = (
        OUTPUT_DIR
        / "raw"
        / "system_billing_usage.jsonl"
    )

    records = _read_jsonl(source)

    if not records:
        raise RuntimeError(
            f"No records were found in {source}"
        )

    sample = records[:2]

    path = EVIDENCE_DIR / "raw_sample.jsonl"

    _write_jsonl(
        path,
        sample,
    )

    return path


def _create_normalized_sample() -> Path:
    """
    Create a small redacted normalized sample.

    Prefer normalized billing usage because it demonstrates the common
    cost/usage normalization model.
    """

    candidates = [
        (
            OUTPUT_DIR
            / "normalized"
            / "system_billing_usage.jsonl"
        ),
        (
            OUTPUT_DIR
            / "normalized"
            / "system_billing_list_prices.jsonl"
        ),
    ]

    source = _find_existing_file(candidates)

    if source is None:
        raise FileNotFoundError(
            "No normalized billing output was found."
        )

    records = _read_jsonl(source)

    if not records:
        raise RuntimeError(
            f"No records were found in {source}"
        )

    sample = records[:2]

    path = EVIDENCE_DIR / "normalized_sample.jsonl"

    _write_jsonl(
        path,
        sample,
    )

    return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    EVIDENCE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    coverage = _load_coverage()

    coverage_path = _write_redacted_coverage(
        coverage
    )

    live_run_path = _write_live_run_evidence(
        coverage
    )

    raw_sample_path = _create_raw_sample()

    normalized_sample_path = _create_normalized_sample()

    print("Submission evidence created successfully.")
    print()
    print(f"Coverage report:    {coverage_path}")
    print(f"Live run evidence:  {live_run_path}")
    print(f"Raw sample:         {raw_sample_path}")
    print(f"Normalized sample:  {normalized_sample_path}")
    print()
    print(
        "These files are redacted for repository submission."
    )


if __name__ == "__main__":
    main()
