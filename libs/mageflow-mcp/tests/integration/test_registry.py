import pytest

from mageflow_mcp.models import PaginatedTaskDefinitionList
from mageflow_mcp.tools.registry import list_registered_tasks
from tests.integration.conftest import DispatchedTasks


@pytest.mark.asyncio(loop_scope="session")
async def test_list_registered_tasks_returns_worker_tasks(
    dispatched_tasks: DispatchedTasks,
):
    result = await list_registered_tasks()
    assert isinstance(result, PaginatedTaskDefinitionList)
    assert result.total_count > 0

    task_names = [item.task_name for item in result.items]

    # Task names are namespaced by Hatchet (e.g. "tests_for_mageflow_mcp_mcp-task1")
    expected_suffixes = [
        "mcp-task1",
        "mcp-task2",
        "mcp-task3",
        "mcp-chain-callback",
        "mcp-fail-task",
        "mcp-logging-task",
    ]
    for expected in expected_suffixes:
        assert any(
            name.endswith(expected) for name in task_names
        ), f"No task ending with '{expected}' found in {task_names}"
