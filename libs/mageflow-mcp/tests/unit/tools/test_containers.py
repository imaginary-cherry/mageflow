"""Unit tests for get_container_summary and list_sub_tasks MCP tool functions."""
from __future__ import annotations

import uuid

import pytest
from thirdmagic.chain.model import ChainTaskSignature
from thirdmagic.signature.status import SignatureStatus
from thirdmagic.swarm.model import SwarmTaskSignature
from thirdmagic.task.model import TaskSignature

from mageflow_mcp.models import ContainerSummary, ErrorResponse, PaginatedSubTaskList
from mageflow_mcp.tools.containers import get_container_summary, list_sub_tasks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_chain(*task_names: str) -> tuple[ChainTaskSignature, list[TaskSignature]]:
    """Create and save a ChainTaskSignature with sub-tasks."""
    subs = [TaskSignature(task_name=name) for name in task_names]
    for sub in subs:
        await sub.asave()
    chain = ChainTaskSignature(task_name="test_chain", tasks=[s.key for s in subs])
    await chain.asave()
    return chain, subs


async def _make_swarm(*task_names: str) -> tuple[SwarmTaskSignature, list[TaskSignature]]:
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
