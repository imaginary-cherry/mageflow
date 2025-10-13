import pytest

import orchestrator
from orchestrator import CommandTaskMessage
from orchestrator import TaskSignature
from orchestrator.hatchet.chain import ChainTaskSignature
from orchestrator.hatchet.config import orchestrator_config
from orchestrator.hatchet.signature import SIGNATURES_NAME_MAPPING
from orchestrator.hatchet.signature import SignatureStatus
from tests.unit.hatchet.conftest import assert_redis_keys_do_not_contain_sub_task_ids


@pytest.mark.asyncio
async def test__chain_signature_create_save_load__input_output_same__sanity(
    redis_client, hatchet_mock
):
    # Arrange
    orchestrator_config.redis_client = redis_client

    # Register ChainTaskSignature in the mapping
    SIGNATURES_NAME_MAPPING["ChainTaskSignature"] = ChainTaskSignature

    @hatchet_mock.task(name="test_task_1")
    def test_task_1(msg):
        return msg

    @hatchet_mock.task(name="test_task_2")
    def test_task_2(msg):
        return msg

    # Create individual task signatures
    task1_signature = await TaskSignature.from_task(test_task_1, arg1="value1")
    task2_signature = await TaskSignature.from_task(test_task_2, arg2="value2")

    workflow_params = {"param1": "value1", "param2": "value2"}
    kwargs = {"arg1": "test", "arg2": 123}
    tasks = [task1_signature.id, task2_signature.id]

    # Act
    original_chain_signature = ChainTaskSignature(
        task_name="test_chain_task",
        kwargs=kwargs,
        workflow_params=workflow_params,
        tasks=tasks,
    )
    await original_chain_signature.save()
    loaded_chain_signature = await TaskSignature.from_id(original_chain_signature.id)

    # Assert
    assert original_chain_signature == loaded_chain_signature


@pytest.mark.asyncio
async def test_chain_stop_signature_changes_all_tasks_status_to_stopped_sanity(
    redis_client, hatchet_mock
):
    # Arrange
    orchestrator_config.redis_client = redis_client
    orchestrator_config.hatchet_client = hatchet_mock

    # Create task signatures for chain
    task_signature_1 = TaskSignature(
        task_name="task1",
        kwargs={},
        model_validators=CommandTaskMessage,
    )
    await task_signature_1.save()

    task_signature_2 = TaskSignature(
        task_name="task2",
        kwargs={},
        model_validators=CommandTaskMessage,
    )
    await task_signature_2.save()

    task_signature_3 = TaskSignature(
        task_name="task3",
        kwargs={},
        model_validators=CommandTaskMessage,
    )
    await task_signature_3.save()

    # Create chain
    chain_signature = await orchestrator.chain(
        [task_signature_1.id, task_signature_2.id, task_signature_3.id]
    )
    expected_stopped_tasks = [
        chain_signature,
        task_signature_1,
        task_signature_2,
        task_signature_3,
    ]

    # Act
    await chain_signature.change_status(SignatureStatus.STOPPED)

    # Assert
    # Verify chain signature status changed to stopped
    for task in expected_stopped_tasks:
        reloaded_task = await TaskSignature.from_id(task.id)
        assert (
            reloaded_task.status == SignatureStatus.STOPPED
        ), f"{task.id} not stopped - {task.task_name}"


@pytest.mark.asyncio
async def test_chain_stop_signature_with_deleted_sub_tasks_does_not_change_status_edge_case(
    redis_client, hatchet_mock
):
    # Arrange
    orchestrator_config.redis_client = redis_client
    orchestrator_config.hatchet_client = hatchet_mock

    # Create task signatures for chain
    task_signature_1 = TaskSignature(
        task_name="task1",
        kwargs={},
        model_validators=CommandTaskMessage,
    )
    await task_signature_1.save()

    task_signature_2 = TaskSignature(
        task_name="task2",
        kwargs={},
        model_validators=CommandTaskMessage,
    )
    await task_signature_2.save()

    # Create chain
    chain_signature = await orchestrator.chain([task_signature_1.id, task_signature_2.id])

    # Delete sub-tasks from Redis (simulate they were removed)
    await task_signature_1.remove()
    await task_signature_2.remove()

    # Act
    await chain_signature.change_status(SignatureStatus.STOPPED)

    # Assert
    # Verify chain signature status changed to stopped
    reloaded_chain = await TaskSignature.from_id(chain_signature.id)
    assert reloaded_chain.status == SignatureStatus.STOPPED

    # Verify deleted sub-tasks don't exist and change_status didn't affect them
    with pytest.raises(Exception):
        await TaskSignature.from_id(task_signature_1.id)

    with pytest.raises(Exception):
        await TaskSignature.from_id(task_signature_2.id)

    # Verify no Redis keys contain the deleted sub-task IDs
    await assert_redis_keys_do_not_contain_sub_task_ids(
        redis_client, [task_signature_1.id, task_signature_2.id]
    )
