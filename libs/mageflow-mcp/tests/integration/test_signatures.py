import pytest

from mageflow_mcp.models import ErrorResponse, PaginatedSignatureList, SignatureInfo
from mageflow_mcp.tools.signatures import get_signature, list_signatures
from tests.integration.conftest import DispatchedTasks
from thirdmagic.signature.status import SignatureStatus


@pytest.mark.asyncio(loop_scope="session")
async def test_get_signature_after_task_run(dispatched_tasks: DispatchedTasks):
    result = await get_signature(dispatched_tasks.task1_sig.key)
    assert isinstance(result, SignatureInfo)
    assert result.key == dispatched_tasks.task1_sig.key
    assert result.task_name.endswith("mcp-task1")
    assert result.status == SignatureStatus.DONE
    assert result.kwargs is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_get_signature_not_found(dispatched_tasks: DispatchedTasks):
    result = await get_signature("nonexistent:key:12345")
    assert isinstance(result, ErrorResponse)
    assert result.error == "key_not_found"


@pytest.mark.asyncio(loop_scope="session")
async def test_list_signatures_returns_all(dispatched_tasks: DispatchedTasks):
    result = await list_signatures()
    assert isinstance(result, PaginatedSignatureList)
    result_keys = [item.key for item in result.items]
    assert dispatched_tasks.task1_sig.key in result_keys
    assert dispatched_tasks.task2_sig.key in result_keys


@pytest.mark.asyncio(loop_scope="session")
async def test_list_signatures_filter_by_status(dispatched_tasks: DispatchedTasks):
    done_result = await list_signatures(status=SignatureStatus.DONE)
    assert isinstance(done_result, PaginatedSignatureList)
    done_keys = [item.key for item in done_result.items]
    assert dispatched_tasks.task1_sig.key in done_keys
    assert dispatched_tasks.fail_sig.key not in done_keys

    failed_result = await list_signatures(status=SignatureStatus.FAILED)
    assert isinstance(failed_result, PaginatedSignatureList)
    failed_keys = [item.key for item in failed_result.items]
    assert dispatched_tasks.fail_sig.key in failed_keys
    assert dispatched_tasks.task1_sig.key not in failed_keys


@pytest.mark.asyncio(loop_scope="session")
async def test_list_signatures_filter_by_task_name(dispatched_tasks: DispatchedTasks):
    # task_name is namespaced by Hatchet (e.g. "namespace_mcp-task1")
    result = await list_signatures(task_name=dispatched_tasks.task1_sig.task_name)
    assert isinstance(result, PaginatedSignatureList)
    result_keys = [item.key for item in result.items]
    assert dispatched_tasks.task1_sig.key in result_keys
    assert dispatched_tasks.task2_sig.key not in result_keys
