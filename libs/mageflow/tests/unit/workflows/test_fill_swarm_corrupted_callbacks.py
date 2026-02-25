import base64

import pytest
from thirdmagic.task import TaskSignature

from mageflow.swarm.workflows import fill_swarm_running_tasks
from tests.unit.workflows.conftest import CompletedSwarmWithSuccessCallback


async def corrupt_model_validators_in_redis(signature_key: str, redis_client):
    invalid_pickle = base64.b64encode(b"invalid_pickle_data").decode("utf-8")
    await redis_client.json().set(signature_key, "$.model_validators", invalid_pickle)


@pytest.mark.asyncio
async def test_activate_success_with_corrupted_callback_model_validators_succeeds(
    completed_swarm_with_success_callback: CompletedSwarmWithSuccessCallback,
    adapter_with_lifecycle,
    redis_client,
):
    # Arrange
    setup = completed_swarm_with_success_callback
    success_callbacks = setup.swarm_task.success_callbacks
    for signature in success_callbacks:
        await corrupt_model_validators_in_redis(signature, redis_client)

    # Act
    await fill_swarm_running_tasks(
        setup.swarm_task_id, setup.max_tasks, setup.lifecycle, setup.logger
    )

    # Assert
    adapter_with_lifecycle.acall_signatures.assert_awaited_once()
    called_signatures = adapter_with_lifecycle.acall_signatures.call_args[0][0]
    assert len(called_signatures) == len(success_callbacks)
    for sig in called_signatures:
        assert sig.key in success_callbacks
        reloaded_callback = await TaskSignature.aget(sig.key)
        assert reloaded_callback.model_validators is None


@pytest.mark.asyncio
async def test_activate_error_with_corrupted_callback_model_validators_succeeds(
    completed_swarm_with_success_callback: CompletedSwarmWithSuccessCallback,
    adapter_with_lifecycle,
    redis_client,
):
    # Arrange
    setup = completed_swarm_with_success_callback
    error_callbacks = setup.swarm_task.success_callbacks
    for signature in error_callbacks:
        await corrupt_model_validators_in_redis(signature, redis_client)

    # Act
    await fill_swarm_running_tasks(
        setup.swarm_task_id, setup.max_tasks, setup.lifecycle, setup.logger
    )

    # Assert
    adapter_with_lifecycle.acall_signatures.assert_awaited_once()
    called_signatures = adapter_with_lifecycle.acall_signatures.call_args[0][0]
    assert len(called_signatures) == len(error_callbacks)
    for sig in called_signatures:
        assert sig.key in error_callbacks
        reloaded_callback = await TaskSignature.aget(sig.key)
        assert reloaded_callback.model_validators is None
