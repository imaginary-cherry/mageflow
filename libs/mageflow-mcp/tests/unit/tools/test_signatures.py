import asyncio

import pytest

from mageflow_mcp.models import ErrorResponse, PaginatedSignatureList, SignatureInfo
from mageflow_mcp.tools.signatures import PAGE_SIZE_MAX, get_signature, list_signatures
from thirdmagic.chain.model import ChainTaskSignature
from thirdmagic.signature.status import SignatureStatus
from thirdmagic.task.model import TaskSignature

# ---------------------------------------------------------------------------
# get_signature tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test__get_signature__valid_task_signature__returns_signature_info():
    """get_signature with a valid TaskSignature key returns a SignatureInfo."""
    sig = TaskSignature(task_name="my_task")
    await sig.asave()

    result = await get_signature(sig.key)

    assert isinstance(result, SignatureInfo)
    assert result.task_name == "my_task"
    assert result.signature_type == "TaskSignature"
    assert result.status == SignatureStatus.PENDING
    assert isinstance(result.kwargs, dict)
    assert result.key == sig.key


@pytest.mark.asyncio
async def test__get_signature__valid_chain_signature__returns_chain_type():
    """get_signature with a valid ChainTaskSignature key returns chain type."""
    chain = ChainTaskSignature(task_name="my_chain")
    await chain.asave()

    result = await get_signature(chain.key)

    assert isinstance(result, SignatureInfo)
    assert result.signature_type == "ChainTaskSignature"
    assert result.task_name == "my_chain"


@pytest.mark.asyncio
async def test__get_signature__nonexistent_key__returns_error_response():
    """get_signature with a nonexistent key returns a structured ErrorResponse."""
    result = await get_signature("TaskSignature:nonexistent-uuid-0000")

    assert isinstance(result, ErrorResponse)
    assert result.error == "key_not_found"
    assert result.suggestion
    assert result.message


@pytest.mark.asyncio
async def test__get_signature__invalid_prefix__returns_error_response():
    """get_signature with an unknown key prefix returns a structured ErrorResponse."""
    result = await get_signature("InvalidModel:abc")

    assert isinstance(result, ErrorResponse)
    assert result.error == "key_not_found"


# ---------------------------------------------------------------------------
# list_signatures tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test__list_signatures__no_filters__returns_paginated_list():
    """list_signatures with no filters returns all signatures paginated."""
    sigs = [TaskSignature(task_name=f"task_{i}") for i in range(3)]
    for sig in sigs:
        await sig.asave()

    result = await list_signatures()

    assert isinstance(result, PaginatedSignatureList)
    assert result.total_count == 3
    assert result.page == 1
    assert len(result.items) == 3


@pytest.mark.asyncio
async def test__list_signatures__status_filter__returns_matching_only():
    """list_signatures with status=DONE returns only DONE signatures."""
    sig_pending = TaskSignature(task_name="pending_task")
    await sig_pending.asave()

    sig_done = TaskSignature(task_name="done_task")
    await sig_done.asave()
    await sig_done.change_status(SignatureStatus.DONE)

    result = await list_signatures(status=SignatureStatus.DONE)

    assert result.total_count == 1
    assert len(result.items) == 1
    assert result.items[0].status == SignatureStatus.DONE
    assert result.items[0].task_name == "done_task"


@pytest.mark.asyncio
async def test__list_signatures__task_name_filter__exact_match():
    """list_signatures with task_name filter returns only exact-name matches."""
    sig_alpha = TaskSignature(task_name="alpha")
    await sig_alpha.asave()

    sig_beta = TaskSignature(task_name="beta")
    await sig_beta.asave()

    result = await list_signatures(task_name="alpha")

    assert result.total_count == 1
    assert result.items[0].task_name == "alpha"


@pytest.mark.asyncio
async def test__list_signatures__pagination__respects_page_size():
    """list_signatures paginates correctly across multiple pages."""
    for i in range(5):
        sig = TaskSignature(task_name=f"paged_task_{i}")
        await sig.asave()

    # Page 1: 2 items
    page1 = await list_signatures(page=1, page_size=2)
    assert len(page1.items) == 2
    assert page1.total_count == 5
    assert page1.total_pages == 3

    # Page 2: 2 items
    page2 = await list_signatures(page=2, page_size=2)
    assert len(page2.items) == 2

    # Page 3: 1 remaining item
    page3 = await list_signatures(page=3, page_size=2)
    assert len(page3.items) == 1


@pytest.mark.asyncio
async def test__list_signatures__page_size_capped_at_max():
    """list_signatures caps page_size at PAGE_SIZE_MAX (50)."""
    result = await list_signatures(page_size=100)

    assert result.page_size == PAGE_SIZE_MAX


@pytest.mark.asyncio
async def test__list_signatures__sorted_by_creation_time_desc():
    """list_signatures returns results sorted by creation_time descending."""
    # Create signatures with a small delay so they get distinct timestamps
    sig1 = TaskSignature(task_name="first")
    await sig1.asave()
    await asyncio.sleep(0.01)

    sig2 = TaskSignature(task_name="second")
    await sig2.asave()
    await asyncio.sleep(0.01)

    sig3 = TaskSignature(task_name="third")
    await sig3.asave()

    result = await list_signatures()

    assert result.total_count == 3
    # Most recent should be first
    creation_times = [item.creation_time for item in result.items]
    assert creation_times == sorted(creation_times, reverse=True)
    assert result.items[0].task_name == "third"
    assert result.items[2].task_name == "first"


@pytest.mark.asyncio
async def test__list_signatures__empty_result__returns_valid_paginated_list():
    """list_signatures on empty Redis returns a valid paginated list with 0 items."""
    result = await list_signatures()

    assert result.total_count == 0
    assert result.items == []
    assert result.total_pages == 1
    assert result.page == 1


# ── Additional edge case and boundary tests ────────────────────────────


@pytest.mark.asyncio
async def test__list_signatures__created_after_filter() -> None:
    """list_signatures with created_after filter returns only matching signatures."""
    from datetime import datetime, timezone

    sig1 = TaskSignature(task_name="old_task")
    await sig1.asave()
    await asyncio.sleep(0.01)

    cutoff_time = datetime.now(timezone.utc)
    await asyncio.sleep(0.01)

    sig2 = TaskSignature(task_name="new_task")
    await sig2.asave()

    result = await list_signatures(created_after=cutoff_time)

    assert isinstance(result, PaginatedSignatureList)
    assert result.total_count == 1
    assert result.items[0].task_name == "new_task"


@pytest.mark.asyncio
async def test__list_signatures__created_before_filter() -> None:
    """list_signatures with created_before filter returns only matching signatures."""
    from datetime import datetime, timezone

    sig1 = TaskSignature(task_name="old_task")
    await sig1.asave()
    await asyncio.sleep(0.01)

    cutoff_time = datetime.now(timezone.utc)
    await asyncio.sleep(0.01)

    sig2 = TaskSignature(task_name="new_task")
    await sig2.asave()

    result = await list_signatures(created_before=cutoff_time)

    assert isinstance(result, PaginatedSignatureList)
    assert result.total_count == 1
    assert result.items[0].task_name == "old_task"


@pytest.mark.asyncio
async def test__list_signatures__created_after_and_before_combined() -> None:
    """list_signatures with both date filters should return signatures in range."""
    from datetime import datetime, timezone

    sig1 = TaskSignature(task_name="before")
    await sig1.asave()
    await asyncio.sleep(0.01)

    start_time = datetime.now(timezone.utc)
    await asyncio.sleep(0.01)

    sig2 = TaskSignature(task_name="in_range")
    await sig2.asave()
    await asyncio.sleep(0.01)

    end_time = datetime.now(timezone.utc)
    await asyncio.sleep(0.01)

    sig3 = TaskSignature(task_name="after")
    await sig3.asave()

    result = await list_signatures(created_after=start_time, created_before=end_time)

    assert isinstance(result, PaginatedSignatureList)
    assert result.total_count == 1
    assert result.items[0].task_name == "in_range"


@pytest.mark.asyncio
async def test__list_signatures__multiple_filters_combined() -> None:
    """list_signatures should correctly apply status and task_name filters together."""
    sig1 = TaskSignature(task_name="target_task")
    await sig1.asave()
    await sig1.change_status(SignatureStatus.DONE)

    sig2 = TaskSignature(task_name="target_task")
    await sig2.asave()
    # sig2 stays PENDING

    sig3 = TaskSignature(task_name="other_task")
    await sig3.asave()
    await sig3.change_status(SignatureStatus.DONE)

    result = await list_signatures(
        status=SignatureStatus.DONE, task_name="target_task"
    )

    assert result.total_count == 1
    assert result.items[0].task_name == "target_task"
    assert result.items[0].status == SignatureStatus.DONE


@pytest.mark.asyncio
async def test__list_signatures__all_signature_types_returned() -> None:
    """list_signatures should return TaskSignature, ChainTaskSignature, and SwarmTaskSignature."""
    task = TaskSignature(task_name="plain_task")
    await task.asave()

    chain = ChainTaskSignature(task_name="chain_task")
    await chain.asave()

    from thirdmagic.swarm.model import SwarmTaskSignature

    swarm = SwarmTaskSignature(
        task_name="swarm_task", tasks=[], publishing_state_id="state:123"
    )
    await swarm.asave()

    result = await list_signatures()

    assert result.total_count == 3
    sig_types = {item.signature_type for item in result.items}
    assert "TaskSignature" in sig_types
    assert "ChainTaskSignature" in sig_types
    assert "SwarmTaskSignature" in sig_types


@pytest.mark.asyncio
async def test__get_signature__swarm_signature_returns_correct_type() -> None:
    """get_signature with SwarmTaskSignature returns correct type."""
    from thirdmagic.swarm.model import SwarmTaskSignature

    swarm = SwarmTaskSignature(
        task_name="test_swarm", tasks=[], publishing_state_id="state:456"
    )
    await swarm.asave()

    result = await get_signature(swarm.key)

    assert isinstance(result, SignatureInfo)
    assert result.signature_type == "SwarmTaskSignature"
    assert result.task_name == "test_swarm"


@pytest.mark.asyncio
async def test__list_signatures__filter_no_matches_all_filters() -> None:
    """list_signatures with filters that match nothing returns empty list."""
    sig = TaskSignature(task_name="existing_task")
    await sig.asave()

    result = await list_signatures(task_name="nonexistent_task_name")

    assert isinstance(result, PaginatedSignatureList)
    assert result.total_count == 0
    assert result.items == []
    assert result.total_pages == 1


@pytest.mark.asyncio
async def test__list_signatures__page_beyond_available_returns_empty() -> None:
    """list_signatures with page beyond total pages returns empty items."""
    for i in range(3):
        sig = TaskSignature(task_name=f"task_{i}")
        await sig.asave()

    result = await list_signatures(page=999, page_size=10)

    assert isinstance(result, PaginatedSignatureList)
    assert len(result.items) == 0
    assert result.total_count == 3


@pytest.mark.asyncio
async def test__get_signature__all_status_types() -> None:
    """get_signature should correctly return all signature status types."""
    statuses = [
        SignatureStatus.PENDING,
        SignatureStatus.ACTIVE,
        SignatureStatus.DONE,
        SignatureStatus.FAILED,
        SignatureStatus.SUSPENDED,
        SignatureStatus.CANCELED,
    ]

    for status in statuses:
        sig = TaskSignature(task_name=f"task_{status.value}")
        await sig.asave()
        await sig.change_status(status)

        result = await get_signature(sig.key)

        assert isinstance(result, SignatureInfo)
        assert result.status == status