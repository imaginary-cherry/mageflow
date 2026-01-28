from unittest.mock import patch, AsyncMock

import pytest

from mageflow.chain.model import ChainTaskSignature
from mageflow.chain.workflows import chain_end_task, chain_error_task
from mageflow.signature.model import TaskSignature
from tests.unit.workflows.conftest import create_chain_test_setup


@pytest.fixture
def mock_remove_task_with_delete():
    async def delete_instead_of_ttl(self):
        await self.adelete()

    with patch.object(TaskSignature, "remove_task", delete_instead_of_ttl):
        yield


@pytest.fixture
def mock_chain_activate_success():
    with patch.object(
        ChainTaskSignature, "activate_success", new_callable=AsyncMock
    ) as mock:
        yield mock


@pytest.fixture
def mock_chain_activate_error():
    with patch.object(
        ChainTaskSignature, "activate_error", new_callable=AsyncMock
    ) as mock:
        yield mock


@pytest.mark.asyncio
async def test_chain_end_crash_at_remove_current_task_retry_succeeds_idempotent(
    mock_remove_task_with_delete,
    mock_chain_activate_success,
):
    # Arrange
    setup = await create_chain_test_setup(num_chain_tasks=3)

    # Act - First call crashes at remove_from_key
    with patch.object(TaskSignature, "remove_from_key", side_effect=RuntimeError):
        with pytest.raises(RuntimeError):
            await chain_end_task(setup.msg, setup.ctx)

    # Assert - activate_success was called (before crash point)
    assert mock_chain_activate_success.call_count == 1

    # Act - Retry succeeds
    await chain_end_task(setup.msg, setup.ctx)

    # Assert - activate_success still called only once (idempotent)
    assert mock_chain_activate_success.call_count == 1


@pytest.mark.asyncio
async def test_chain_end_run_twice_callback_activated_once_idempotent(
    mock_remove_task_with_delete,
    mock_chain_activate_success,
):
    # Arrange
    setup = await create_chain_test_setup(num_chain_tasks=3)

    # Act
    await chain_end_task(setup.msg, setup.ctx)
    await chain_end_task(setup.msg, setup.ctx)

    # Assert
    assert mock_chain_activate_success.call_count == 1


@pytest.mark.asyncio
async def test__chain_end_fail_on_remove_task__able_to_delete(
    redis_client,
    mock_remove_task_with_delete,
    mock_chain_activate_success,
):
    # Arrange
    setup = await create_chain_test_setup(num_chain_tasks=3)

    # Act
    with pytest.raises(RuntimeError):
        with patch.object(
            ChainTaskSignature, "remove_task", side_effect=RuntimeError()
        ):
            await chain_end_task(setup.msg, setup.ctx)

    sub_tasks_exists = await redis_client.exists(*setup.chain_signature.tasks)
    assert not sub_tasks_exists
    await chain_end_task(setup.msg, setup.ctx)
    chain_exists = await redis_client.exists(*setup.chain_signature.key)
    assert not chain_exists


@pytest.mark.asyncio
async def test_chain_error_crash_at_remove_current_task_retry_succeeds_idempotent(
    mock_remove_task_with_delete,
    mock_chain_activate_error,
):
    # Arrange
    setup = await create_chain_test_setup(num_chain_tasks=3)

    # Act - First call crashes at remove_from_key
    with patch.object(TaskSignature, "remove_from_key", side_effect=RuntimeError):
        with pytest.raises(RuntimeError):
            await chain_error_task(setup.msg, setup.ctx)

    # Assert - activate_error was called (before crash point)
    assert mock_chain_activate_error.call_count == 1

    # Act - Retry succeeds
    await chain_error_task(setup.msg, setup.ctx)

    # Assert - activate_error still called only once (idempotent)
    assert mock_chain_activate_error.call_count == 1


@pytest.mark.asyncio
async def test_chain_error_run_twice_callback_activated_once_idempotent(
    mock_remove_task_with_delete,
    mock_chain_activate_error,
):
    # Arrange
    setup = await create_chain_test_setup(num_chain_tasks=3)

    # Act
    await chain_error_task(setup.msg, setup.ctx)
    await chain_error_task(setup.msg, setup.ctx)

    # Assert
    assert mock_chain_activate_error.call_count == 1


@pytest.mark.asyncio
async def test__chain_error_fail_on_remove_task__able_to_delete(
    redis_client,
    mock_remove_task_with_delete,
    mock_chain_activate_error,
):
    # Arrange
    setup = await create_chain_test_setup(num_chain_tasks=3)

    # Act
    with pytest.raises(RuntimeError):
        with patch.object(
            ChainTaskSignature, "remove_task", side_effect=RuntimeError()
        ):
            await chain_error_task(setup.msg, setup.ctx)

    sub_tasks_exists = await redis_client.exists(*setup.chain_signature.tasks)
    assert not sub_tasks_exists
    await chain_end_task(setup.msg, setup.ctx)
    chain_exists = await redis_client.exists(*setup.chain_signature.key)
    assert not chain_exists
