from hatchet_sdk import Hatchet

from mageflow_mcp.adapters.base import BaseMCPAdapter
from mageflow_mcp.models import LogEntry


class HatchetMCPAdapter(BaseMCPAdapter):
    """MCP adapter that retrieves execution logs and run status from the Hatchet API.

    Wraps a Hatchet SDK instance to provide log retrieval and run status checks.
    No retry logic is implemented here — the Hatchet SDK's LogsClient and RunsClient
    already apply tenacity-based retries internally (5 attempts, exponential jitter).

    Exceptions are intentionally not caught in this adapter. The tool layer
    (tools/logs.py) is responsible for mapping exceptions to ErrorResponse objects
    with user-facing messages. This keeps the adapter thin and honest about failures.
    """

    def __init__(self, hatchet: Hatchet) -> None:
        self.hatchet = hatchet

    async def get_logs(self, task_run_id: str) -> list[LogEntry]:
        """Retrieve log entries for a Hatchet task run.

        Calls the Hatchet REST API log endpoint and maps V1LogLine rows to
        LogEntry objects. Returns an empty list if the run has no log lines.

        Args:
            task_run_id: The Hatchet task run UUID.

        Returns:
            List of LogEntry objects in chronological order (as returned by Hatchet).
            May be empty if no logs have been produced yet.

        Raises:
            UnauthorizedException: HTTP 401 — missing or invalid HATCHET_CLIENT_TOKEN.
            ForbiddenException: HTTP 403 — token valid but lacks permission.
            ServiceException: HTTP 5xx — Hatchet server error or unreachable.
            Exception: Any other unexpected error.
        """
        result = await self.hatchet.logs.aio_list(task_run_id=task_run_id)
        rows = result.rows or []
        return [
            LogEntry(
                line=row.message,
                timestamp=row.created_at,
                level=row.level.value if row.level else None,
            )
            for row in rows
        ]

    async def get_run_status(self, task_run_id: str) -> str:
        """Return the Hatchet task run status as a string.

        Args:
            task_run_id: The Hatchet task run UUID.

        Returns:
            Status string: one of 'QUEUED', 'RUNNING', 'COMPLETED', 'CANCELLED', 'FAILED'.
            Returns 'RUNNING' if the status field is None (safe non-terminal default).

        Raises:
            Exception: Any error from the Hatchet API (network, auth, 5xx).
        """
        summary = await self.hatchet.runs.aio_get_task_run(task_run_id)
        return summary.status.value if summary.status else "RUNNING"
