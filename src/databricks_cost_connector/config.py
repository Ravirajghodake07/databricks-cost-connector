from dataclasses import dataclass
from datetime import datetime, timezone
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    databricks_host: str
    databricks_token: str
    warehouse_name: str = "Serverless Starter Warehouse"
    start_time: datetime | None = None
    end_time: datetime | None = None


def parse_datetime(value: str | None, variable_name: str) -> datetime | None:
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            f"{variable_name} must be an ISO-8601 timestamp, "
            f"for example 2026-10-01T00:00:00Z."
        ) from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def load_settings() -> Settings:
    load_dotenv()

    host = os.getenv("DATABRICKS_HOST")
    token = os.getenv("DATABRICKS_TOKEN")

    if not host:
        raise ValueError("DATABRICKS_HOST is not configured.")

    if not token:
        raise ValueError("DATABRICKS_TOKEN is not configured.")

    start_time = parse_datetime(
        os.getenv("DATABRICKS_START_TIME"),
        "DATABRICKS_START_TIME",
    )
    end_time = parse_datetime(
        os.getenv("DATABRICKS_END_TIME"),
        "DATABRICKS_END_TIME",
    )

    if start_time and end_time and start_time >= end_time:
        raise ValueError(
            "DATABRICKS_START_TIME must be earlier than DATABRICKS_END_TIME."
        )

    warehouse_name = os.getenv("DATABRICKS_WAREHOUSE_NAME") or (
        "Serverless Starter Warehouse"
    )

    return Settings(
        databricks_host=host,
        databricks_token=token,
        warehouse_name=warehouse_name,
        start_time=start_time,
        end_time=end_time,
    )
