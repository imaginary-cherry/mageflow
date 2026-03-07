from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from mageflow_mcp.models import ErrorResponse, LogEntry, LogsResponse
from mageflow_mcp.tools.logs import get_logs
from thirdmagic.task.model import TaskSignature

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


# ── Additional edge case and boundary tests ────────────────────────────


@pytest.mark.asyncio
async def test__get_logs__empty_logs__returns_empty_response() -> None:
    """get_logs with no log entries returns valid empty LogsResponse."""
    sig = TaskSignature(task_name="my_task")
    sig.worker_task_id = "run-uuid-empty"
    await sig.asave()

    adapter = make_adapter(logs=[], run_status="COMPLETED")
    ctx = make_ctx(adapter)

    result = await get_logs(sig.key, ctx)

    assert isinstance(result, LogsResponse)
    assert len(result.items) == 0
    assert result.total_count == 0
    assert result.total_pages == 1
    assert result.is_complete is True


@pytest.mark.asyncio
async def test__get_logs__case_insensitive_level_filter() -> None:
    """get_logs should handle case-insensitive level filtering."""
    sig = TaskSignature(task_name="my_task")
    sig.worker_task_id = "run-uuid-case"
    await sig.asave()

    adapter = make_adapter(
        logs=[
            make_log_entry("info log", "INFO"),
            make_log_entry("error log", "ERROR"),
        ]
    )
    ctx = make_ctx(adapter)

    # Test uppercase filter
    result_upper = await get_logs(sig.key, ctx, level="INFO")
    assert isinstance(result_upper, LogsResponse)
    assert result_upper.total_count == 1

    # Test lowercase filter
    result_lower = await get_logs(sig.key, ctx, level="info")
    assert isinstance(result_lower, LogsResponse)
    assert result_lower.total_count == 1


@pytest.mark.asyncio
async def test__get_logs__warning_normalizes_to_warn() -> None:
    """get_logs should normalize 'warning' level to 'warn'."""
    sig = TaskSignature(task_name="my_task")
    sig.worker_task_id = "run-uuid-warning"
    await sig.asave()

    adapter = make_adapter(
        logs=[
            make_log_entry("warn log", "warn"),
            make_log_entry("info log", "INFO"),
        ]
    )
    ctx = make_ctx(adapter)

    result = await get_logs(sig.key, ctx, level="warning")

    assert isinstance(result, LogsResponse)
    assert result.total_count == 1
    assert result.items[0].line == "warn log"


@pytest.mark.asyncio
async def test__get_logs__all_valid_log_levels() -> None:
    """get_logs should accept all valid log levels: debug, info, warn, error."""
    sig = TaskSignature(task_name="my_task")
    sig.worker_task_id = "run-uuid-levels"
    await sig.asave()

    valid_levels = ["debug", "info", "warn", "error"]
    for level in valid_levels:
        adapter = make_adapter(
            logs=[make_log_entry(f"{level} message", level.upper())]
        )
        ctx = make_ctx(adapter)

        result = await get_logs(sig.key, ctx, level=level)

        assert isinstance(result, LogsResponse), f"Failed for level: {level}"
        assert result.total_count == 1


@pytest.mark.asyncio
async def test__get_logs__pagination_last_page_partial() -> None:
    """get_logs should correctly handle last page with fewer items than page_size."""
    sig = TaskSignature(task_name="my_task")
    sig.worker_task_id = "run-uuid-partial"
    await sig.asave()

    adapter = make_adapter(
        logs=[make_log_entry(f"line {i}") for i in range(7)],
        run_status="RUNNING",
    )
    ctx = make_ctx(adapter)

    # Page 3 with page_size=3 should have only 1 item (7 total: 3+3+1)
    result = await get_logs(sig.key, ctx, page=3, page_size=3)

    assert isinstance(result, LogsResponse)
    assert len(result.items) == 1
    assert result.total_count == 7
    assert result.total_pages == 3


@pytest.mark.asyncio
async def test__get_logs__page_beyond_total__returns_empty() -> None:
    """get_logs with page number beyond total pages returns empty items."""
    sig = TaskSignature(task_name="my_task")
    sig.worker_task_id = "run-uuid-beyond"
    await sig.asave()

    adapter = make_adapter(
        logs=[make_log_entry("line 1"), make_log_entry("line 2")]
    )
    ctx = make_ctx(adapter)

    result = await get_logs(sig.key, ctx, page=999, page_size=10)

    assert isinstance(result, LogsResponse)
    assert len(result.items) == 0
    assert result.total_count == 2


@pytest.mark.asyncio
async def test__get_logs__page_size_exceeds_max__caps_at_max() -> None:
    """get_logs should cap page_size at PAGE_SIZE_MAX."""
    from mageflow_mcp.tools.signatures import PAGE_SIZE_MAX

    sig = TaskSignature(task_name="my_task")
    sig.worker_task_id = "run-uuid-cap"
    await sig.asave()

    adapter = make_adapter(logs=[make_log_entry(f"line {i}") for i in range(100)])
    ctx = make_ctx(adapter)

    result = await get_logs(sig.key, ctx, page_size=1000)

    assert isinstance(result, LogsResponse)
    assert result.page_size == PAGE_SIZE_MAX


@pytest.mark.asyncio
async def test__get_logs__all_terminal_statuses_return_complete_true() -> None:
    """get_logs should return is_complete=True for all terminal statuses."""
    sig = TaskSignature(task_name="my_task")
    sig.worker_task_id = "run-uuid-terminal"
    await sig.asave()

    terminal_statuses = ["COMPLETED", "CANCELLED", "FAILED"]
    for status in terminal_statuses:
        adapter = make_adapter(logs=[make_log_entry("test")], run_status=status)
        ctx = make_ctx(adapter)

        result = await get_logs(sig.key, ctx)

        assert isinstance(result, LogsResponse), f"Failed for status: {status}"
        assert result.is_complete is True, f"Expected complete for status: {status}"


@pytest.mark.asyncio
async def test__get_logs__level_filter_with_none_level_entries() -> None:
    """get_logs level filter should handle log entries with None level."""
    sig = TaskSignature(task_name="my_task")
    sig.worker_task_id = "run-uuid-none-level"
    await sig.asave()

    adapter = make_adapter(
        logs=[
            LogEntry(line="no level", level=None),
            make_log_entry("info level", "INFO"),
        ]
    )
    ctx = make_ctx(adapter)

    result = await get_logs(sig.key, ctx, level="info")

    assert isinstance(result, LogsResponse)
    assert result.total_count == 1
    assert result.items[0].line == "info level"


@pytest.mark.asyncio
async def test__get_logs__multiple_filters_combined() -> None:
    """get_logs should apply level filter and pagination together correctly."""
    sig = TaskSignature(task_name="my_task")
    sig.worker_task_id = "run-uuid-combined"
    await sig.asave()

    adapter = make_adapter(
        logs=[
            make_log_entry("error 1", "ERROR"),
            make_log_entry("info 1", "INFO"),
            make_log_entry("error 2", "ERROR"),
            make_log_entry("info 2", "INFO"),
            make_log_entry("error 3", "ERROR"),
        ]
    )
    ctx = make_ctx(adapter)

    result = await get_logs(sig.key, ctx, level="error", page=1, page_size=2)

    assert isinstance(result, LogsResponse)
    assert result.total_count == 3  # 3 ERROR entries total
    assert len(result.items) == 2  # First page has 2 items
    assert result.total_pages == 2
    for item in result.items:
        assert item.level == "ERROR"