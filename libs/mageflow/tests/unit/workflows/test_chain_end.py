import pytest

from mageflow.chain.workflows import chain_end_task
from tests.unit.assertions import assert_task_has_short_ttl
from tests.unit.workflows.conftest import create_chain_test_setup


@pytest.mark.asyncio
async def test_chain_end_task_sanity(redis_client, adapter_with_lifecycle, mock_logger):
    # Arrange
    results = {"status": "success", "value": 42}
    setup = await create_chain_test_setup(num_chain_tasks=3, results=results, adapter=adapter_with_lifecycle, logger=mock_logger)

    # Act
    await chain_end_task(setup.msg.chain_results, setup.lifecycle_manager, setup.logger)

    # Assert
    adapter_with_lifecycle.acall_signatures.assert_awaited_once_with(
        [setup.success_callback], results, True
    )
    await assert_task_has_short_ttl(redis_client, setup.chain_signature.key)

    for task in setup.chain_tasks:
        await assert_task_has_short_ttl(redis_client, task.key)
