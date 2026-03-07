import pytest

from mageflow_mcp.models import PaginatedTaskDefinitionList
from mageflow_mcp.tools.registry import list_registered_tasks
from mageflow_mcp.tools.signatures import PAGE_SIZE_MAX
from thirdmagic.task_def import MageflowTaskDefinition


@pytest.mark.asyncio
async def test__list_registered_tasks__returns_all_entries():
    """list_registered_tasks with no filters returns all task definition entries."""
    names = ["task_alpha", "task_beta", "task_gamma"]
    for name in names:
        d = MageflowTaskDefinition(mageflow_task_name=name, task_name=f"{name}Task")
        await d.asave()

    result = await list_registered_tasks()

    assert isinstance(result, PaginatedTaskDefinitionList)
    assert result.total_count == 3
    assert len(result.items) == 3


@pytest.mark.asyncio
async def test__list_registered_tasks__returns_correct_fields():
    """list_registered_tasks projects entries to TaskDefinitionInfo with correct fields."""
    d = MageflowTaskDefinition(
        mageflow_task_name="send_email",
        task_name="SendEmailTask",
        retries=3,
    )
    await d.asave()

    result = await list_registered_tasks()

    assert isinstance(result, PaginatedTaskDefinitionList)
    assert result.total_count == 1
    item = result.items[0]
    assert item.mageflow_task_name == "send_email"
    assert item.task_name == "SendEmailTask"
    assert item.retries == 3


@pytest.mark.asyncio
async def test__list_registered_tasks__pagination():
    """list_registered_tasks respects page and page_size parameters."""
    for i in range(5):
        d = MageflowTaskDefinition(
            mageflow_task_name=f"task_{i}",
            task_name=f"Task{i}",
        )
        await d.asave()

    # Page 1: 2 items out of 5
    page1 = await list_registered_tasks(page=1, page_size=2)
    assert len(page1.items) == 2
    assert page1.total_count == 5
    assert page1.total_pages == 3

    # Page 3: 1 remaining item
    page3 = await list_registered_tasks(page=3, page_size=2)
    assert len(page3.items) == 1


@pytest.mark.asyncio
async def test__list_registered_tasks__empty_registry():
    """list_registered_tasks on empty Redis returns valid paginated list with 0 items."""
    result = await list_registered_tasks()

    assert isinstance(result, PaginatedTaskDefinitionList)
    assert result.total_count == 0
    assert result.items == []
    assert result.total_pages == 1


@pytest.mark.asyncio
async def test__list_registered_tasks__page_size_capped():
    """list_registered_tasks caps page_size at PAGE_SIZE_MAX (50)."""
    result = await list_registered_tasks(page_size=100)

    assert result.page_size == PAGE_SIZE_MAX


# ── Additional edge case and boundary tests ────────────────────────────


@pytest.mark.asyncio
async def test__list_registered_tasks__page_beyond_total_returns_empty():
    """list_registered_tasks with page beyond total pages returns empty items."""
    for i in range(3):
        d = MageflowTaskDefinition(
            mageflow_task_name=f"task_{i}",
            task_name=f"Task{i}",
        )
        await d.asave()

    result = await list_registered_tasks(page=999, page_size=10)

    assert isinstance(result, PaginatedTaskDefinitionList)
    assert len(result.items) == 0
    assert result.total_count == 3


@pytest.mark.asyncio
async def test__list_registered_tasks__single_page_exact_fit():
    """list_registered_tasks with exactly page_size items returns correct pagination."""
    for i in range(20):  # Exactly PAGE_SIZE_DEFAULT
        d = MageflowTaskDefinition(
            mageflow_task_name=f"task_{i}",
            task_name=f"Task{i}",
        )
        await d.asave()

    result = await list_registered_tasks(page=1, page_size=20)

    assert result.total_count == 20
    assert len(result.items) == 20
    assert result.total_pages == 1


@pytest.mark.asyncio
async def test__list_registered_tasks__last_page_partial():
    """list_registered_tasks last page should have fewer items than page_size."""
    for i in range(7):
        d = MageflowTaskDefinition(
            mageflow_task_name=f"task_{i}",
            task_name=f"Task{i}",
        )
        await d.asave()

    # Page 2 with page_size=5 should have 2 items (7 total: 5+2)
    result = await list_registered_tasks(page=2, page_size=5)

    assert len(result.items) == 2
    assert result.total_count == 7
    assert result.total_pages == 2


@pytest.mark.asyncio
async def test__list_registered_tasks__task_with_special_characters():
    """list_registered_tasks should handle task names with special characters."""
    d = MageflowTaskDefinition(
        mageflow_task_name="task-with-dashes_and_underscores.dots",
        task_name="TaskWith$pecial!Chars@123",
        retries=5,
    )
    await d.asave()

    result = await list_registered_tasks()

    assert result.total_count == 1
    item = result.items[0]
    assert item.mageflow_task_name == "task-with-dashes_and_underscores.dots"
    assert item.task_name == "TaskWith$pecial!Chars@123"


@pytest.mark.asyncio
async def test__list_registered_tasks__very_high_retry_count():
    """list_registered_tasks should handle very high retry counts."""
    d = MageflowTaskDefinition(
        mageflow_task_name="high_retry_task",
        task_name="HighRetryTask",
        retries=999999,
    )
    await d.asave()

    result = await list_registered_tasks()

    assert result.total_count == 1
    assert result.items[0].retries == 999999


@pytest.mark.asyncio
async def test__list_registered_tasks__negative_retries():
    """list_registered_tasks should handle negative retry values."""
    d = MageflowTaskDefinition(
        mageflow_task_name="negative_retry_task",
        task_name="NegativeRetryTask",
        retries=-1,
    )
    await d.asave()

    result = await list_registered_tasks()

    assert result.total_count == 1
    assert result.items[0].retries == -1