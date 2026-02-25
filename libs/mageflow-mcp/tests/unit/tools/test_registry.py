import pytest
from thirdmagic.task_def import MageflowTaskDefinition

from mageflow_mcp.models import PaginatedTaskDefinitionList
from mageflow_mcp.tools.registry import list_registered_tasks
from mageflow_mcp.tools.signatures import PAGE_SIZE_MAX


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
