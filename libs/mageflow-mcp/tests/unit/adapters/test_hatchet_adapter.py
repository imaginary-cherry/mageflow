"""Unit tests for HatchetMCPAdapter using mocked Hatchet SDK."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from mageflow_mcp.adapters.hatchet import HatchetMCPAdapter
from mageflow_mcp.models import LogEntry


@pytest.mark.asyncio
async def test__hatchet_adapter__get_logs__returns_log_entries() -> None:
    """get_logs maps V1LogLine rows to LogEntry objects."""
    row = MagicMock()
    row.message = "Processing item 42"
    row.created_at = datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc)
    row.level = MagicMock()
    row.level.value = "INFO"

    result_obj = MagicMock()
    result_obj.rows = [row]

    hatchet = MagicMock()
    hatchet.logs = MagicMock()
    hatchet.logs.aio_list = AsyncMock(return_value=result_obj)

    adapter = HatchetMCPAdapter(hatchet)
    entries = await adapter.get_logs("run-uuid-123")

    assert len(entries) == 1
    assert isinstance(entries[0], LogEntry)
    assert entries[0].line == "Processing item 42"
    assert entries[0].level == "INFO"
    assert entries[0].timestamp == datetime(2026, 2, 24, 12, 0, 0, tzinfo=timezone.utc)
    hatchet.logs.aio_list.assert_awaited_once_with(
        task_run_id="run-uuid-123", limit=1000
    )


@pytest.mark.asyncio
async def test__hatchet_adapter__get_logs__empty_rows_returns_empty_list() -> None:
    """get_logs returns an empty list when result.rows is None."""
    result_obj = MagicMock()
    result_obj.rows = None

    hatchet = MagicMock()
    hatchet.logs = MagicMock()
    hatchet.logs.aio_list = AsyncMock(return_value=result_obj)

    adapter = HatchetMCPAdapter(hatchet)
    entries = await adapter.get_logs("run-uuid-empty")

    assert entries == []


@pytest.mark.asyncio
async def test__hatchet_adapter__get_logs__level_none_maps_to_none() -> None:
    """get_logs maps a row with level=None to LogEntry.level=None."""
    row = MagicMock()
    row.message = "no level"
    row.created_at = None
    row.level = None

    result_obj = MagicMock()
    result_obj.rows = [row]

    hatchet = MagicMock()
    hatchet.logs = MagicMock()
    hatchet.logs.aio_list = AsyncMock(return_value=result_obj)

    adapter = HatchetMCPAdapter(hatchet)
    entries = await adapter.get_logs("run-uuid-nolevel")

    assert len(entries) == 1
    assert entries[0].level is None


@pytest.mark.asyncio
async def test__hatchet_adapter__get_run_status__returns_status_string() -> None:
    """get_run_status returns the V1TaskStatus value as a string."""
    summary = MagicMock()
    summary.status = MagicMock()
    summary.status.value = "COMPLETED"

    hatchet = MagicMock()
    hatchet.runs = MagicMock()
    hatchet.runs.aio_get_task_run = AsyncMock(return_value=summary)

    adapter = HatchetMCPAdapter(hatchet)
    status = await adapter.get_run_status("run-uuid-done")

    assert status == "COMPLETED"
    hatchet.runs.aio_get_task_run.assert_awaited_once_with("run-uuid-done")


@pytest.mark.asyncio
async def test__hatchet_adapter__get_run_status__none_status_returns_running() -> None:
    """get_run_status returns 'RUNNING' when summary.status is None."""
    summary = MagicMock()
    summary.status = None

    hatchet = MagicMock()
    hatchet.runs = MagicMock()
    hatchet.runs.aio_get_task_run = AsyncMock(return_value=summary)

    adapter = HatchetMCPAdapter(hatchet)
    status = await adapter.get_run_status("run-uuid-unknown")

    assert status == "RUNNING"
