from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from thirdmagic.chain.model import ChainTaskSignature
from thirdmagic.container import ContainerTaskSignature
from thirdmagic.signature import Signature

from mageflow.chain.workflows import chain_end_task, chain_error_task
from tests.unit.workflows.conftest import create_chain_test_setup


@pytest.fixture
def mock_remove_task_with_delete():
    async def delete_instead_of_ttl(self):
        await self.adelete()

    with patch.object(Signature, "remove_task", delete_instead_of_ttl):
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
    adapter_with_lifecycle,
    mock_logger,
):
    # Arrange
    setup = await create_chain_test_setup(
        num_chain_tasks=3, adapter=adapter_with_lifecycle, logger=mock_logger
    )

    # Act - First call crashes at remove_references
    with patch.object(
        ContainerTaskSignature, "remove_references", side_effect=RuntimeError
    ):
        with pytest.raises(RuntimeError):
            await chain_end_task(
                setup.msg.chain_results, setup.lifecycle_manager, setup.logger
            )

    # Assert - activate_success was called (before crash point)
    assert mock_chain_activate_success.call_count == 1

    # Act - Retry succeeds
    await chain_end_task(setup.msg.chain_results, setup.lifecycle_manager, setup.logger)

    # Assert - activate_success called again on retry (no idempotency guard in task_success)
    assert mock_chain_activate_success.call_count == 2


@pytest.mark.asyncio
async def test_chain_end_run_twice_callback_activated_once_idempotent(
    mock_remove_task_with_delete,
    mock_chain_activate_success,
    adapter_with_lifecycle,
    mock_logger,
):
    # Arrange
    setup = await create_chain_test_setup(
        num_chain_tasks=3, adapter=adapter_with_lifecycle, logger=mock_logger
    )

    # Act
    await chain_end_task(setup.msg.chain_results, setup.lifecycle_manager, setup.logger)
    lifecycle2 = await adapter_with_lifecycle.lifecycle_from_signature(
        setup.msg, MagicMock(), setup.chain_signature.key
    )
    await chain_end_task(setup.msg.chain_results, lifecycle2, setup.logger)

    # Assert
    assert mock_chain_activate_success.call_count == 1


@pytest.mark.asyncio
async def test__chain_end_fail_on_remove_task__able_to_delete(
    redis_client,
    mock_remove_task_with_delete,
    mock_chain_activate_success,
    adapter_with_lifecycle,
    mock_logger,
):
    # Arrange
    setup = await create_chain_test_setup(
        num_chain_tasks=3, adapter=adapter_with_lifecycle, logger=mock_logger
    )

    # Act
    with pytest.raises(RuntimeError):
        with patch.object(
            ChainTaskSignature, "remove_task", side_effect=RuntimeError()
        ):
            await chain_end_task(
                setup.msg.chain_results, setup.lifecycle_manager, setup.logger
            )

    sub_tasks_exists = await redis_client.exists(*setup.chain_signature.tasks)
    assert not sub_tasks_exists
    await chain_end_task(setup.msg.chain_results, setup.lifecycle_manager, setup.logger)
    chain_exists = await redis_client.exists(*setup.chain_signature.key)
    assert not chain_exists


@pytest.mark.asyncio
async def test_chain_error_crash_at_remove_current_task_retry_succeeds_idempotent(
    mock_remove_task_with_delete,
    mock_chain_activate_error,
    adapter_with_lifecycle,
    mock_logger,
):
    # Arrange
    setup = await create_chain_test_setup(
        num_chain_tasks=3, adapter=adapter_with_lifecycle, logger=mock_logger
    )

    # Act - First call crashes at remove_references
    with patch.object(
        ContainerTaskSignature, "remove_references", side_effect=RuntimeError
    ):
        with pytest.raises(RuntimeError):
            await chain_error_task(
                setup.error_msg.chain_task_id,
                setup.error_msg.original_msg,
                setup.error_msg.error,
                setup.lifecycle_manager,
                setup.logger,
            )

    # Assert - activate_error was called (before crash point)
    assert mock_chain_activate_error.call_count == 1

    # Act - Retry succeeds
    await chain_error_task(
        setup.error_msg.chain_task_id,
        setup.error_msg.original_msg,
        setup.error_msg.error,
        setup.lifecycle_manager,
        setup.logger,
    )

    # Assert - activate_error called again on retry (no idempotency guard in task_failed)
    assert mock_chain_activate_error.call_count == 2


@pytest.mark.asyncio
async def test_chain_error_run_twice_callback_activated_once_idempotent(
    mock_remove_task_with_delete,
    mock_chain_activate_error,
    adapter_with_lifecycle,
    mock_logger,
):
    # Arrange
    setup = await create_chain_test_setup(
        num_chain_tasks=3, adapter=adapter_with_lifecycle, logger=mock_logger
    )

    # Act
    await chain_error_task(
        setup.error_msg.chain_task_id,
        setup.error_msg.original_msg,
        setup.error_msg.error,
        setup.lifecycle_manager,
        setup.logger,
    )
    lifecycle2 = await adapter_with_lifecycle.lifecycle_from_signature(
        setup.error_msg, MagicMock(), setup.chain_signature.key
    )
    await chain_error_task(
        setup.error_msg.chain_task_id,
        setup.error_msg.original_msg,
        setup.error_msg.error,
        lifecycle2,
        setup.logger,
    )

    # Assert
    assert mock_chain_activate_error.call_count == 1


@pytest.mark.asyncio
async def test__chain_error_fail_on_remove_task__able_to_delete(
    redis_client,
    mock_remove_task_with_delete,
    mock_chain_activate_error,
    adapter_with_lifecycle,
    mock_logger,
):
    # Arrange
    setup = await create_chain_test_setup(
        num_chain_tasks=3, adapter=adapter_with_lifecycle, logger=mock_logger
    )

    # Act
    with pytest.raises(RuntimeError):
        with patch.object(
            ChainTaskSignature, "remove_task", side_effect=RuntimeError()
        ):
            await chain_error_task(
                setup.error_msg.chain_task_id,
                setup.error_msg.original_msg,
                setup.error_msg.error,
                setup.lifecycle_manager,
                setup.logger,
            )

    sub_tasks_exists = await redis_client.exists(*setup.chain_signature.tasks)
    assert not sub_tasks_exists
    await chain_end_task(setup.msg.chain_results, setup.lifecycle_manager, setup.logger)
    chain_exists = await redis_client.exists(*setup.chain_signature.key)
    assert not chain_exists
