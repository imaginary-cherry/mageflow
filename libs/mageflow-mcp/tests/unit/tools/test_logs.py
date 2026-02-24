"""Unit tests for the get_logs MCP tool function."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from hatchet_sdk.clients.rest.exceptions import ServiceException, UnauthorizedException
from thirdmagic.chain.model import ChainTaskSignature
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
    assert result.worker_task_id == "run-uuid-123"


@pytest.mark.asyncio
async def test__get_logs__no_worker_task_id__returns_not_dispatched_error() -> None:
    """get_logs returns task_not_dispatched ErrorResponse when worker_task_id is absent."""
    sig = TaskSignature(task_name="my_task")
    await sig.asave()

    adapter = make_adapter()
    ctx = make_ctx(adapter)

    result = await get_logs(sig.key, ctx)

    assert isinstance(result, ErrorResponse)
    assert result.error == "task_not_dispatched"
    adapter.get_logs.assert_not_called()


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
async def test__get_logs__auth_failure__returns_auth_error() -> None:
    """get_logs returns auth_failure ErrorResponse when adapter raises UnauthorizedException."""
    sig = TaskSignature(task_name="my_task")
    sig.worker_task_id = "run-uuid-auth"
    await sig.asave()

    adapter = AsyncMock()
    adapter.get_logs.side_effect = UnauthorizedException(status=401, reason="Unauthorized")
    ctx = make_ctx(adapter)

    result = await get_logs(sig.key, ctx)

    assert isinstance(result, ErrorResponse)
    assert result.error == "auth_failure"


@pytest.mark.asyncio
async def test__get_logs__service_exception__returns_unavailable_error() -> None:
    """get_logs returns hatchet_unavailable ErrorResponse when adapter raises ServiceException."""
    sig = TaskSignature(task_name="my_task")
    sig.worker_task_id = "run-uuid-svc"
    await sig.asave()

    adapter = AsyncMock()
    adapter.get_logs.side_effect = ServiceException(status=500, reason="Internal Server Error")
    ctx = make_ctx(adapter)

    result = await get_logs(sig.key, ctx)

    assert isinstance(result, ErrorResponse)
    assert result.error == "hatchet_unavailable"


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


# ---------------------------------------------------------------------------
# Container signature tests
# ---------------------------------------------------------------------------


async def _make_chain_with_worker_ids(
    sub_task_names: list[str],
    dispatched_indices: list[int],
) -> tuple[ChainTaskSignature, list[TaskSignature]]:
    """Create a chain with sub-tasks; set worker_task_id on the specified indices."""
    subs = [TaskSignature(task_name=name) for name in sub_task_names]
    for i, sub in enumerate(subs):
        if i in dispatched_indices:
            sub.worker_task_id = f"worker-uuid-{i}"
        await sub.asave()
    chain = ChainTaskSignature(task_name="test_chain", tasks=[s.key for s in subs])
    await chain.asave()
    return chain, subs


@pytest.mark.asyncio
async def test__get_logs__chain_container__groups_logs_by_sub_task() -> None:
    """get_logs with a ChainTaskSignature groups logs by sub-task with separator entries."""
    chain, subs = await _make_chain_with_worker_ids(
        sub_task_names=["sub_a", "sub_b"],
        dispatched_indices=[0, 1],
    )

    adapter = AsyncMock()

    def get_logs_side_effect(task_run_id: str) -> list[LogEntry]:
        if task_run_id == "worker-uuid-0":
            return [make_log_entry("sub_a log 1"), make_log_entry("sub_a log 2")]
        elif task_run_id == "worker-uuid-1":
            return [make_log_entry("sub_b log 1")]
        return []

    adapter.get_logs.side_effect = get_logs_side_effect
    adapter.get_run_status.return_value = "COMPLETED"
    ctx = make_ctx(adapter)

    result = await get_logs(chain.key, ctx)

    assert isinstance(result, LogsResponse)
    # Should have separators + log entries: 1 separator + 2 logs + 1 separator + 1 log = 5
    assert result.total_count == 5

    # Verify separator entries exist
    separator_lines = [item for item in result.items if item.line.startswith("--- Sub-task:")]
    assert len(separator_lines) == 2

    # Verify sub_task_id grouping
    sub_a_entries = [item for item in result.items if item.sub_task_id == subs[0].key]
    sub_b_entries = [item for item in result.items if item.sub_task_id == subs[1].key]
    assert len(sub_a_entries) == 3  # separator + 2 logs
    assert len(sub_b_entries) == 2  # separator + 1 log

    # Verify is_complete
    assert result.is_complete is True


@pytest.mark.asyncio
async def test__get_logs__container_sub_task_not_dispatched__shows_marker() -> None:
    """get_logs with a chain where only one sub-task is dispatched shows not-dispatched marker."""
    chain, subs = await _make_chain_with_worker_ids(
        sub_task_names=["sub_dispatched", "sub_pending"],
        dispatched_indices=[0],  # only first sub-task is dispatched
    )

    adapter = AsyncMock()
    adapter.get_logs.return_value = [make_log_entry("dispatched log")]
    adapter.get_run_status.return_value = "RUNNING"
    ctx = make_ctx(adapter)

    result = await get_logs(chain.key, ctx)

    assert isinstance(result, LogsResponse)

    # The not-dispatched sub-task should have a marker entry containing "not dispatched"
    not_dispatched_entries = [
        item for item in result.items if "not dispatched" in item.line
    ]
    assert len(not_dispatched_entries) == 1

    # is_complete should be False (non-dispatched sub-task + RUNNING status)
    assert result.is_complete is False
