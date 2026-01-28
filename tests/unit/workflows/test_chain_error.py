import pytest

from mageflow.chain.workflows import chain_error_task
from mageflow.signature.consts import TASK_ID_PARAM_NAME
from tests.unit.assertions import assert_task_deleted, assert_task_has_short_ttl
from tests.unit.workflows.conftest import create_chain_test_setup


@pytest.mark.asyncio
async def test_chain_error_task_sanity(mock_workflow_run):
    # Arrange
    setup = await create_chain_test_setup(num_chain_tasks=3)

    # Act
    await chain_error_task(setup.msg, setup.ctx)

    # Assert
    assert len(mock_workflow_run) == 1
    triggered_signature_id = mock_workflow_run[0]._task_ctx[TASK_ID_PARAM_NAME]
    assert triggered_signature_id == setup.error_callback.key

    await assert_task_has_short_ttl(setup.chain_signature.key)
    await assert_task_has_short_ttl(setup.current_task.key)

    for task in setup.chain_tasks:
        await assert_task_has_short_ttl(task.key)
