from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any


def json_default(value: Any) -> str:
    """Serialize Decimal and datetime without converting money to float."""
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def write_jsonl(
    path: Path,
    records: list[dict[str, Any]],
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                    default=json_default,
                )
                + "\n"
            )
    return path


def write_raw_records(
    output_dir: Path,
    source_name: str,
    records: list[dict[str, Any]],
) -> Path:
    raw_dir = output_dir / "raw"
    safe_name = source_name.replace(".", "_")
    return write_jsonl(raw_dir / f"{safe_name}.jsonl", records)


def write_normalized_records(
    output_dir: Path,
    source_name: str,
    records: list[dict[str, Any]],
) -> Path:
    normalized_dir = output_dir / "normalized"
    safe_name = source_name.replace(".", "_")
    return write_jsonl(normalized_dir / f"{safe_name}.jsonl", records)


def write_coverage_report(
    output_dir: Path,
    rows: list[dict[str, Any]],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "coverage_report.json"
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(
            rows,
            file,
            indent=2,
            ensure_ascii=False,
            default=json_default,
        )
    return output_path
