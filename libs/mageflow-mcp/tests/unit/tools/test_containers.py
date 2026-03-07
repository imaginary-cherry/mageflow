import uuid

import pytest

from mageflow_mcp.models import ContainerSummary, ErrorResponse, PaginatedSubTaskList
from mageflow_mcp.tools.containers import get_container_summary, list_sub_tasks
from thirdmagic.chain.model import ChainTaskSignature
from thirdmagic.signature.status import SignatureStatus
from thirdmagic.swarm.model import SwarmTaskSignature
from thirdmagic.task.model import TaskSignature

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_chain(
    *task_names: str,
) -> tuple[ChainTaskSignature, list[TaskSignature]]:
    """Create and save a ChainTaskSignature with sub-tasks."""
    subs = [TaskSignature(task_name=name) for name in task_names]
    for sub in subs:
        await sub.asave()
    chain = ChainTaskSignature(task_name="test_chain", tasks=[s.key for s in subs])
    await chain.asave()
    return chain, subs


async def _make_swarm(
    *task_names: str,
) -> tuple[SwarmTaskSignature, list[TaskSignature]]:
    """Create and save a SwarmTaskSignature with sub-tasks."""
    subs = [TaskSignature(task_name=name) for name in task_names]
    for sub in subs:
        await sub.asave()
    swarm = SwarmTaskSignature(
        task_name="test_swarm",
        tasks=[s.key for s in subs],
        publishing_state_id=str(uuid.uuid4()),
    )
    await swarm.asave()
    return swarm, subs


# ---------------------------------------------------------------------------
# get_container_summary tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test__get_container_summary__chain_with_mixed_statuses__returns_correct_counts():
    """get_container_summary counts sub-tasks by status correctly for a ChainTaskSignature."""
    chain, subs = await _make_chain("sub_pending", "sub_done", "sub_failed")
    await subs[1].change_status(SignatureStatus.DONE)
    await subs[2].change_status(SignatureStatus.FAILED)

    result = await get_container_summary(chain.key)

    assert isinstance(result, ContainerSummary)
    assert result.total == 3
    assert result.pending == 1
    assert result.done == 1
    assert result.failed == 1
    assert result.active == 0
    assert result.suspended == 0
    assert result.canceled == 0


@pytest.mark.asyncio
async def test__get_container_summary__swarm__returns_summary():
    """get_container_summary returns ContainerSummary with SwarmTaskSignature type."""
    swarm, subs = await _make_swarm("swarm_task_a", "swarm_task_b")

    result = await get_container_summary(swarm.key)

    assert isinstance(result, ContainerSummary)
    assert result.signature_type == "SwarmTaskSignature"
    assert result.total == 2
    assert result.pending == 2


@pytest.mark.asyncio
async def test__get_container_summary__nonexistent_key__returns_error():
    """get_container_summary returns key_not_found ErrorResponse for nonexistent key."""
    result = await get_container_summary("ChainTaskSignature:nonexistent-uuid-0000")

    assert isinstance(result, ErrorResponse)
    assert result.error == "key_not_found"
    assert result.message
    assert result.suggestion


@pytest.mark.asyncio
async def test__get_container_summary__non_container_key__returns_not_a_container_error():
    """get_container_summary returns not_a_container ErrorResponse for a plain TaskSignature key."""
    task_sig = TaskSignature(task_name="plain_task")
    await task_sig.asave()

    result = await get_container_summary(task_sig.key)

    assert isinstance(result, ErrorResponse)
    assert result.error == "not_a_container"
    assert result.message
    assert result.suggestion


@pytest.mark.asyncio
async def test__get_container_summary__empty_container__returns_zero_counts():
    """get_container_summary with a chain that has no sub-tasks returns all zeros."""
    chain = ChainTaskSignature(task_name="empty_chain", tasks=[])
    await chain.asave()

    result = await get_container_summary(chain.key)

    assert isinstance(result, ContainerSummary)
    assert result.total == 0
    assert result.pending == 0
    assert result.active == 0
    assert result.done == 0
    assert result.failed == 0
    assert result.suspended == 0
    assert result.canceled == 0


# ---------------------------------------------------------------------------
# list_sub_tasks tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test__list_sub_tasks__no_filter__returns_all_paginated():
    """list_sub_tasks with no status filter returns all sub-tasks paginated."""
    chain, subs = await _make_chain("t1", "t2", "t3")

    result = await list_sub_tasks(chain.key)

    assert isinstance(result, PaginatedSubTaskList)
    assert result.total_count == 3
    assert len(result.items) == 3
    assert result.page == 1


@pytest.mark.asyncio
async def test__list_sub_tasks__status_filter__returns_matching_only():
    """list_sub_tasks with status=DONE returns only DONE sub-tasks."""
    chain, subs = await _make_chain("pending_a", "pending_b", "done_c")
    await subs[2].change_status(SignatureStatus.DONE)

    result = await list_sub_tasks(chain.key, status=SignatureStatus.DONE)

    assert isinstance(result, PaginatedSubTaskList)
    assert result.total_count == 1
    assert len(result.items) == 1
    assert result.items[0].status == SignatureStatus.DONE


@pytest.mark.asyncio
async def test__list_sub_tasks__pagination__respects_page_size():
    """list_sub_tasks paginates correctly with page_size=2 across 5 sub-tasks."""
    chain, subs = await _make_chain("t0", "t1", "t2", "t3", "t4")

    result = await list_sub_tasks(chain.key, page=1, page_size=2)

    assert isinstance(result, PaginatedSubTaskList)
    assert len(result.items) == 2
    assert result.total_count == 5
    assert result.total_pages == 3
    assert result.page_size == 2


@pytest.mark.asyncio
async def test__list_sub_tasks__nonexistent_container__returns_error():
    """list_sub_tasks returns key_not_found ErrorResponse for a nonexistent container key."""
    result = await list_sub_tasks("ChainTaskSignature:nonexistent-container")

    assert isinstance(result, ErrorResponse)
    assert result.error == "key_not_found"
    assert result.message
    assert result.suggestion


@pytest.mark.asyncio
async def test__list_sub_tasks__non_container__returns_not_a_container_error():
    """list_sub_tasks returns not_a_container ErrorResponse for a plain TaskSignature key."""
    task_sig = TaskSignature(task_name="plain_task")
    await task_sig.asave()

    result = await list_sub_tasks(task_sig.key)

    assert isinstance(result, ErrorResponse)
    assert result.error == "not_a_container"
    assert result.message
    assert result.suggestion


# ── Additional edge case and boundary tests ────────────────────────────


@pytest.mark.asyncio
async def test__get_container_summary__container_with_all_statuses__counts_correctly():
    """get_container_summary should count all status types correctly."""
    chain, subs = await _make_chain("s1", "s2", "s3", "s4", "s5", "s6")
    await subs[0].change_status(SignatureStatus.PENDING)
    await subs[1].change_status(SignatureStatus.ACTIVE)
    await subs[2].change_status(SignatureStatus.DONE)
    await subs[3].change_status(SignatureStatus.FAILED)
    await subs[4].change_status(SignatureStatus.SUSPENDED)
    await subs[5].change_status(SignatureStatus.CANCELED)

    result = await get_container_summary(chain.key)

    assert isinstance(result, ContainerSummary)
    assert result.total == 6
    assert result.pending == 1
    assert result.active == 1
    assert result.done == 1
    assert result.failed == 1
    assert result.suspended == 1
    assert result.canceled == 1


@pytest.mark.asyncio
async def test__list_sub_tasks__large_page_number_returns_empty():
    """list_sub_tasks with page beyond available pages returns empty items."""
    chain, subs = await _make_chain("t1", "t2")

    result = await list_sub_tasks(chain.key, page=999, page_size=10)

    assert isinstance(result, PaginatedSubTaskList)
    assert len(result.items) == 0
    assert result.total_count == 2
    assert result.page == 999


@pytest.mark.asyncio
async def test__list_sub_tasks__page_size_exceeds_max__caps_to_max():
    """list_sub_tasks with page_size > PAGE_SIZE_MAX caps at PAGE_SIZE_MAX."""
    from mageflow_mcp.tools.signatures import PAGE_SIZE_MAX

    chain, subs = await _make_chain("t1", "t2", "t3")

    result = await list_sub_tasks(chain.key, page_size=1000)

    assert isinstance(result, PaginatedSubTaskList)
    assert result.page_size == PAGE_SIZE_MAX


@pytest.mark.asyncio
async def test__list_sub_tasks__filter_status_with_no_matches__returns_empty():
    """list_sub_tasks filtering by status with no matches returns empty list."""
    chain, subs = await _make_chain("t1", "t2", "t3")
    # All are PENDING by default

    result = await list_sub_tasks(chain.key, status=SignatureStatus.FAILED)

    assert isinstance(result, PaginatedSubTaskList)
    assert result.total_count == 0
    assert len(result.items) == 0
    assert result.total_pages == 1


@pytest.mark.asyncio
async def test__list_sub_tasks__single_item_container__pagination_works():
    """list_sub_tasks with single sub-task should paginate correctly."""
    chain, subs = await _make_chain("single")

    result = await list_sub_tasks(chain.key, page=1, page_size=10)

    assert isinstance(result, PaginatedSubTaskList)
    assert result.total_count == 1
    assert len(result.items) == 1
    assert result.total_pages == 1


@pytest.mark.asyncio
async def test__list_sub_tasks__page_size_one_multiple_pages():
    """list_sub_tasks with page_size=1 should correctly paginate multiple items."""
    chain, subs = await _make_chain("t1", "t2", "t3")

    page1 = await list_sub_tasks(chain.key, page=1, page_size=1)
    page2 = await list_sub_tasks(chain.key, page=2, page_size=1)
    page3 = await list_sub_tasks(chain.key, page=3, page_size=1)

    assert len(page1.items) == 1
    assert len(page2.items) == 1
    assert len(page3.items) == 1
    assert page1.total_pages == 3
    # All pages should have different items
    keys = {page1.items[0].key, page2.items[0].key, page3.items[0].key}
    assert len(keys) == 3


@pytest.mark.asyncio
async def test__get_container_summary__swarm_with_all_done__correct_counts():
    """get_container_summary for swarm with all tasks done."""
    swarm, subs = await _make_swarm("s1", "s2", "s3")
    for sub in subs:
        await sub.change_status(SignatureStatus.DONE)

    result = await get_container_summary(swarm.key)

    assert isinstance(result, ContainerSummary)
    assert result.signature_type == "SwarmTaskSignature"
    assert result.total == 3
    assert result.done == 3
    assert result.pending == 0
    assert result.active == 0


@pytest.mark.asyncio
async def test__list_sub_tasks__empty_swarm__returns_empty_list():
    """list_sub_tasks for empty swarm returns valid empty paginated list."""
    swarm = SwarmTaskSignature(
        task_name="empty_swarm",
        tasks=[],
        publishing_state_id="state:empty",
    )
    await swarm.asave()

    result = await list_sub_tasks(swarm.key)

    assert isinstance(result, PaginatedSubTaskList)
    assert result.total_count == 0
    assert len(result.items) == 0
    assert result.total_pages == 1


@pytest.mark.asyncio
async def test__list_sub_tasks__status_filter_with_pagination():
    """list_sub_tasks with status filter should paginate filtered results correctly."""
    chain, subs = await _make_chain("p1", "p2", "d1", "d2", "d3")
    # Mark 3 as DONE
    await subs[2].change_status(SignatureStatus.DONE)
    await subs[3].change_status(SignatureStatus.DONE)
    await subs[4].change_status(SignatureStatus.DONE)

    result = await list_sub_tasks(
        chain.key, status=SignatureStatus.DONE, page=1, page_size=2
    )

    assert isinstance(result, PaginatedSubTaskList)
    assert result.total_count == 3
    assert len(result.items) == 2
    assert result.total_pages == 2
    for item in result.items:
        assert item.status == SignatureStatus.DONE