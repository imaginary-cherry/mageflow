import math

from mcp.server.fastmcp import Context
from rapyer.errors import RapyerError
from rapyer.errors.base import KeyNotFound
from thirdmagic.task import TaskSignature

from mageflow_mcp.models import ErrorResponse, LogsResponse
from mageflow_mcp.tools.signatures import PAGE_SIZE_DEFAULT, PAGE_SIZE_MAX

_TERMINAL_STATUSES = {"COMPLETED", "CANCELLED", "FAILED"}
_VALID_LEVELS = {"debug", "info", "warn", "error"}


async def get_logs(
    signature_id: str,
    ctx: Context,
    level: str | None = None,
    page: int = 1,
    page_size: int = PAGE_SIZE_DEFAULT,
) -> LogsResponse | ErrorResponse:
    """
    Retrieve execution log lines for a dispatched task signature.
    Fetch the logs of the worker recorded for the signature task.
    """
    # Get adapter from context
    adapter = ctx.request_context.lifespan_context.get("adapter")
    if adapter is None:
        return ErrorResponse(
            error="adapter_not_configured",
            message="The Hatchet adapter is not configured. The get_logs tool requires a valid HATCHET_CLIENT_TOKEN.",
            suggestion="Set the HATCHET_CLIENT_TOKEN environment variable and restart the MCP server.",
        )
    effective_page_size = min(page_size, PAGE_SIZE_MAX)

    # Resolve signature from Redis
    try:
        sig = await TaskSignature.aget(signature_id)
    except KeyNotFound:
        return ErrorResponse(
            error="key_not_found",
            message=f"Signature '{signature_id}' does not exist or has expired.",
            suggestion="Use list_signatures to browse available signature IDs.",
        )
    except RapyerError:
        return ErrorResponse(
            error="redis_error",
            message="Could not retrieve signature from Redis.",
            suggestion="Verify that the MCP server started successfully with a valid REDIS_URL.",
        )

    # Fetch logs from adapter
    try:
        all_logs = await adapter.get_logs(sig.worker_task_id)
    except Exception as e:
        return ErrorResponse(
            error="unexpected_error",
            message=f"An unexpected error occurred while fetching logs from Hatchet. {e}",
            suggestion="Check the server logs for details.",
        )

    # Determine is_complete (simple task)
    is_complete = False
    try:
        run_status = await adapter.get_run_status(sig.worker_task_id)
        is_complete = run_status in _TERMINAL_STATUSES
    except Exception:
        pass  # is_complete stays False — non-fatal

    # Apply level filter (Python-side)
    if level is not None:
        normalized = level.lower()
        if normalized == "warning":
            normalized = "warn"
        if normalized not in _VALID_LEVELS:
            return ErrorResponse(
                error="invalid_filter",
                message=f"Unknown log level '{level}'. Valid values: debug, info, warn, error.",
                suggestion="Use one of: debug, info, warn, error.",
            )
        all_logs = [e for e in all_logs if (e.level or "").lower() == normalized]

    # Paginate
    total = len(all_logs)
    start = (page - 1) * effective_page_size
    page_logs = all_logs[start : start + effective_page_size]

    return LogsResponse(
        items=page_logs,
        total_count=total,
        page=page,
        page_size=effective_page_size,
        total_pages=math.ceil(total / effective_page_size) if total > 0 else 1,
        is_complete=is_complete,
    )
