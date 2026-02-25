import pytest

from mageflow_mcp.models import (
    ContainerSummary,
    ErrorResponse,
    PaginatedSubTaskList,
)
from mageflow_mcp.tools.containers import get_container_summary, list_sub_tasks
from thirdmagic.signature.status import SignatureStatus
from tests.integration.conftest import DispatchedTasks


@pytest.mark.asyncio(loop_scope="session")
async def test_get_container_summary_chain(dispatched_tasks: DispatchedTasks):
    result = await get_container_summary(dispatched_tasks.chain_sig.key)
    assert isinstance(result, ContainerSummary)
    assert result.container_key == dispatched_tasks.chain_sig.key
    assert result.signature_type == "ChainTaskSignature"
    assert result.total == 3
    assert result.done == 3


@pytest.mark.asyncio(loop_scope="session")
async def test_list_sub_tasks_chain(dispatched_tasks: DispatchedTasks):
    result = await list_sub_tasks(dispatched_tasks.chain_sig.key)
    assert isinstance(result, PaginatedSubTaskList)
    assert result.total_count == 3

    sub_keys = [item.key for item in result.items]
    for sig in dispatched_tasks.chain_task_sigs:
        assert sig.key in sub_keys

    for item in result.items:
        assert item.status == SignatureStatus.DONE


@pytest.mark.asyncio(loop_scope="session")
async def test_list_sub_tasks_with_status_filter(dispatched_tasks: DispatchedTasks):
    done_result = await list_sub_tasks(
        dispatched_tasks.chain_sig.key, status=SignatureStatus.DONE
    )
    assert isinstance(done_result, PaginatedSubTaskList)
    assert done_result.total_count == 3

    pending_result = await list_sub_tasks(
        dispatched_tasks.chain_sig.key, status=SignatureStatus.PENDING
    )
    assert isinstance(pending_result, PaginatedSubTaskList)
    assert pending_result.total_count == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_get_container_summary_not_found(dispatched_tasks: DispatchedTasks):
    result = await get_container_summary("nonexistent:container:key:12345")
    assert isinstance(result, ErrorResponse)
    assert result.error == "key_not_found"
