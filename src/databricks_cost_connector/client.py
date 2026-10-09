from databricks.sdk import WorkspaceClient

from .config import Settings


def create_workspace_client(settings: Settings) -> WorkspaceClient:
    """Create an authenticated Databricks workspace client from settings."""
    return WorkspaceClient(
        host=settings.databricks_host,
        token=settings.databricks_token,
    )
