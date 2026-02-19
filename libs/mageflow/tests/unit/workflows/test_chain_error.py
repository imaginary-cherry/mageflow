import pytest
from hatchet_sdk.runnables.types import EmptyModel

from mageflow.chain.workflows import chain_error_task
from tests.unit.assertions import assert_task_has_short_ttl
from tests.unit.workflows.conftest import create_chain_test_setup


@pytest.mark.asyncio
async def test_chain_error_task_sanity(redis_client, adapter_with_lifecycle):
    # Arrange
    setup = await create_chain_test_setup(num_chain_tasks=3)

    # Act
    await chain_error_task(setup.error_msg, setup.ctx)

    # Assert
    adapter_with_lifecycle.acall_signatures.assert_awaited_once_with(
        [setup.error_callback], [EmptyModel(**setup.error_msg.original_msg)], False
    )

    await assert_task_has_short_ttl(redis_client, setup.chain_signature.key)

    for task in setup.chain_tasks:
        await assert_task_has_short_ttl(redis_client, task.key)
