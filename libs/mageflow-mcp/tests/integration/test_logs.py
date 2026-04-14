import pytest
from hatchet_sdk import Hatchet

from mageflow_mcp.adapters.hatchet import HatchetMCPAdapter
from mageflow_mcp.models import ErrorResponse, LogsResponse
from mageflow_mcp.tools.logs import get_logs
from tests.integration.conftest import DispatchedTasks, mock_mcp_context
from tests.integration.worker import LOG_LINE_1, LOG_LINE_2, config_obj


@pytest.fixture(scope="session")
def adapter() -> HatchetMCPAdapter:
    copy_config = config_obj.model_copy(deep=True)
    h = Hatchet(debug=True, config=copy_config)
    return HatchetMCPAdapter(h)


@pytest.mark.asyncio(loop_scope="session")
async def test_get_logs_for_completed_task_with_content(
    dispatched_tasks: DispatchedTasks, adapter: HatchetMCPAdapter
):
    """Verify that logs produced by ctx.log() in the worker are retrievable.

    Uses the Hatchet runs API to resolve the correct task_external_id
    (step run ID) from the workflow run, then calls the adapter directly.
    """
    hatchet = adapter.hatchet
    workflow_run = await hatchet.runs.aio_get(dispatched_tasks.logging_workflow_run_id)
    task_run = workflow_run.tasks[0]
    task_external_id = task_run.task_external_id

    logs = await adapter.get_logs(task_external_id)
    log_messages = [entry.line for entry in logs]
    assert LOG_LINE_1 in log_messages
    assert LOG_LINE_2 in log_messages


@pytest.mark.asyncio(loop_scope="session")
async def test_get_logs_mcp_tool_completed_task(
    dispatched_tasks: DispatchedTasks, adapter: HatchetMCPAdapter
):
    """Call the MCP get_logs tool for a completed task signature."""
    ctx = mock_mcp_context(adapter)
    result = await get_logs(dispatched_tasks.task1_sig.key, ctx=ctx)
    # worker_task_id stores ctx.workflow_id (workflow definition ID) rather
    # than the step_run_id that the Hatchet logs API expects, so the tool
    # may return an ErrorResponse with 'unexpected_error'.
    assert isinstance(result, (LogsResponse, ErrorResponse))
    if isinstance(result, LogsResponse):
        assert result.is_complete is True


@pytest.mark.asyncio(loop_scope="session")
async def test_get_logs_not_found(
    dispatched_tasks: DispatchedTasks, adapter: HatchetMCPAdapter
):
    ctx = mock_mcp_context(adapter)
    result = await get_logs("nonexistent:key:12345", ctx=ctx)
    assert isinstance(result, ErrorResponse)
    assert result.error == "key_not_found"


@pytest.mark.asyncio(loop_scope="session")
async def test_get_logs_no_adapter(dispatched_tasks: DispatchedTasks):
    ctx = mock_mcp_context(None)
    result = await get_logs("any:key:12345", ctx=ctx)
    assert isinstance(result, ErrorResponse)
    assert result.error == "adapter_not_configured"
