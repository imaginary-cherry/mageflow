"""Unit tests for the get_logs MCP tool function."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from thirdmagic.task.model import TaskSignature

from mageflow_mcp.models import ErrorResponse, LogEntry, LogsResponse
from mageflow_mcp.tools.logs import get_logs

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_ctx(adapter: object) -> MagicMock:
    """Build a minimal FastMCP Context mock with a lifespan-injected adapter."""
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"adapter": adapter}
    return ctx


def make_adapter(
    logs: list[LogEntry] | None = None,
    run_status: str = "COMPLETED",
) -> AsyncMock:
    """Create an AsyncMock adapter with pre-configured return values."""
    adapter = AsyncMock()
    adapter.get_logs.return_value = logs or []
    adapter.get_run_status.return_value = run_status
    return adapter


def make_log_entry(line: str, level: str | None = None) -> LogEntry:
    """Create a LogEntry for use in adapter mock return values."""
    return LogEntry(
        line=line,
        timestamp=datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc),
        level=level,
    )


# ---------------------------------------------------------------------------
# Simple TaskSignature tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test__get_logs__valid_signature_with_worker_task_id__returns_logs() -> None:
    """get_logs returns LogsResponse with log entries for a dispatched signature."""
    sig = TaskSignature(task_name="my_task")
    sig.worker_task_id = "run-uuid-123"
    await sig.asave()

    adapter = make_adapter(
        logs=[make_log_entry("hello", "INFO")],
        run_status="COMPLETED",
    )
    ctx = make_ctx(adapter)

    result = await get_logs(sig.key, ctx)

    assert isinstance(result, LogsResponse)
    assert len(result.items) == 1
    assert result.items[0].line == "hello"
    assert result.is_complete is True


@pytest.mark.asyncio
async def test__get_logs__nonexistent_signature__returns_key_not_found() -> None:
    """get_logs returns key_not_found ErrorResponse for a nonexistent Redis key."""
    adapter = make_adapter()
    ctx = make_ctx(adapter)

    result = await get_logs("TaskSignature:nonexistent-key-9999", ctx)

    assert isinstance(result, ErrorResponse)
    assert result.error == "key_not_found"


@pytest.mark.asyncio
async def test__get_logs__level_filter__returns_matching_only() -> None:
    """get_logs with level='error' returns only ERROR-level entries."""
    sig = TaskSignature(task_name="my_task")
    sig.worker_task_id = "run-uuid-filter"
    await sig.asave()

    adapter = make_adapter(
        logs=[
            make_log_entry("info line", "INFO"),
            make_log_entry("error line", "ERROR"),
            make_log_entry("another info", "INFO"),
        ],
        run_status="RUNNING",
    )
    ctx = make_ctx(adapter)

    result = await get_logs(sig.key, ctx, level="error")

    assert isinstance(result, LogsResponse)
    assert result.total_count == 1
    assert result.items[0].line == "error line"


@pytest.mark.asyncio
async def test__get_logs__invalid_level__returns_error() -> None:
    """get_logs returns invalid_filter ErrorResponse for unknown log level."""
    sig = TaskSignature(task_name="my_task")
    sig.worker_task_id = "run-uuid-level-err"
    await sig.asave()

    adapter = make_adapter(logs=[make_log_entry("log line")])
    ctx = make_ctx(adapter)

    result = await get_logs(sig.key, ctx, level="trace")

    assert isinstance(result, ErrorResponse)
    assert result.error == "invalid_filter"


@pytest.mark.asyncio
async def test__get_logs__pagination__respects_page_size() -> None:
    """get_logs paginates correctly with page=1, page_size=2 across 5 entries."""
    sig = TaskSignature(task_name="my_task")
    sig.worker_task_id = "run-uuid-paginate"
    await sig.asave()

    adapter = make_adapter(
        logs=[make_log_entry(f"line {i}") for i in range(5)],
        run_status="RUNNING",
    )
    ctx = make_ctx(adapter)

    result = await get_logs(sig.key, ctx, page=1, page_size=2)

    assert isinstance(result, LogsResponse)
    assert len(result.items) == 2
    assert result.total_count == 5
    assert result.total_pages == 3


@pytest.mark.asyncio
async def test__get_logs__unexpected_exception__returns_unexpected_error() -> None:
    """get_logs returns unexpected_error ErrorResponse for unhandled exceptions."""
    sig = TaskSignature(task_name="my_task")
    sig.worker_task_id = "run-uuid-boom"
    await sig.asave()

    adapter = AsyncMock()
    adapter.get_logs.side_effect = RuntimeError("boom")
    ctx = make_ctx(adapter)

    result = await get_logs(sig.key, ctx)

    assert isinstance(result, ErrorResponse)
    assert result.error == "unexpected_error"


@pytest.mark.asyncio
async def test__get_logs__is_complete_false_when_running() -> None:
    """get_logs returns is_complete=False when run status is RUNNING."""
    sig = TaskSignature(task_name="my_task")
    sig.worker_task_id = "run-uuid-running"
    await sig.asave()

    adapter = make_adapter(
        logs=[make_log_entry("in progress")],
        run_status="RUNNING",
    )
    ctx = make_ctx(adapter)

    result = await get_logs(sig.key, ctx)

    assert isinstance(result, LogsResponse)
    assert result.is_complete is False


@pytest.mark.asyncio
async def test__get_logs__is_complete_defaults_false_on_status_error() -> None:
    """get_logs returns is_complete=False when get_run_status raises an exception."""
    sig = TaskSignature(task_name="my_task")
    sig.worker_task_id = "run-uuid-status-fail"
    await sig.asave()

    adapter = AsyncMock()
    adapter.get_logs.return_value = [make_log_entry("a log")]
    adapter.get_run_status.side_effect = Exception("network failure")
    ctx = make_ctx(adapter)

    result = await get_logs(sig.key, ctx)

    assert isinstance(result, LogsResponse)
    assert result.is_complete is False
    assert len(result.items) == 1


@pytest.mark.asyncio
async def test__get_logs__adapter_not_configured__returns_error() -> None:
    """get_logs returns adapter_not_configured ErrorResponse when adapter is None."""
    sig = TaskSignature(task_name="my_task")
    sig.worker_task_id = "run-uuid-noadapter"
    await sig.asave()

    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"adapter": None}

    result = await get_logs(sig.key, ctx)

    assert isinstance(result, ErrorResponse)
    assert result.error == "adapter_not_configured"
