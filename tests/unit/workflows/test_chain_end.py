import pytest

from mageflow.signature.consts import TASK_ID_PARAM_NAME
from mageflow.chain.workflows import chain_end_task
from tests.unit.assertions import assert_task_has_short_ttl
from tests.unit.workflows.conftest import create_chain_test_setup


@pytest.mark.asyncio
async def test_chain_end_task_sanity(mock_workflow_run):
    # Arrange
    setup = await create_chain_test_setup(
        num_chain_tasks=3,
        results={"status": "success", "value": 42},
    )

    # Act
    await chain_end_task(setup.msg, setup.ctx)

    # Assert
    assert len(mock_workflow_run) == 1
    triggered_signature_id = mock_workflow_run[0]._task_ctx[TASK_ID_PARAM_NAME]
    assert triggered_signature_id == setup.success_callback.key

    await assert_task_has_short_ttl(setup.chain_signature.key)
    await assert_task_has_short_ttl(setup.current_task.key)

    for task in setup.chain_tasks:
        await assert_task_has_short_ttl(task.key)
