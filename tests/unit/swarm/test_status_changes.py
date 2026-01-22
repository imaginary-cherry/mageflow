import pytest

import mageflow
from mageflow.signature.model import TaskSignature
from mageflow.signature.status import SignatureStatus
from mageflow.swarm.model import SwarmTaskSignature
from tests.integration.hatchet.models import ContextMessage
from tests.unit.assertions import assert_redis_keys_do_not_contain_sub_task_ids
from tests.unit.assertions import (
    assert_tasks_changed_status,
    assert_tasks_not_exists,
)
from tests.unit.conftest import ChainTestData


@pytest.mark.asyncio
async def test_swarm_pause_signature_changes_all_swarm_and_chain_tasks_status_to_paused_sanity(
    chain_with_tasks: ChainTestData,
):
    # Arrange
    chain_signature = chain_with_tasks.chain_signature

    # Create additional swarm task signatures (not part of chain)
    swarm_task_signature_1 = await mageflow.sign(
        "swarm_task_1", model_validators=ContextMessage
    )
    swarm_task_signature_2 = await mageflow.sign(
        "swarm_task_2", model_validators=ContextMessage
    )

    # Create a swarm with both chain and individual tasks
    swarm_signature = await mageflow.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        tasks=[
            chain_signature,
            swarm_task_signature_1,
            swarm_task_signature_2,
        ],
    )

    expected_paused_tasks = [
        swarm_signature,
        chain_signature,
        swarm_task_signature_1,
        swarm_task_signature_2,
        *chain_with_tasks.task_signatures,
    ]

    # Act
    await swarm_signature.change_status(SignatureStatus.SUSPENDED)

    # Assert
    # Verify swarm signature status changed to paused
    for task in expected_paused_tasks:
        updated_signature = await TaskSignature.get_safe(task.key)
        assert (
            updated_signature.task_status.status == SignatureStatus.SUSPENDED
        ), f"{task.key} not paused - {task.task_name}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["task_names", "tasks_to_delete_indices", "new_status"],
    [
        [
            ["swarm_task_1", "swarm_task_2", "swarm_task_3"],
            [],
            SignatureStatus.SUSPENDED,
        ],
        [
            ["swarm_task_1", "swarm_task_2"],
            [0, 1],
            SignatureStatus.SUSPENDED,
        ],
        [
            ["swarm_task_1", "swarm_task_2", "swarm_task_3"],
            [0, 2],
            SignatureStatus.SUSPENDED,
        ],
    ],
)
async def test_swarm_change_status_with_optional_deleted_sub_tasks_edge_case(
    redis_client,
    task_names: list[str],
    tasks_to_delete_indices: list[int],
    new_status: SignatureStatus,
):
    # Arrange
    # Create task signatures via API
    task_signatures = [await mageflow.sign(name) for name in task_names]

    # Create a swarm with task signatures
    swarm_signature = await mageflow.swarm(
        task_name="test_swarm",
        tasks=task_signatures,
    )

    # Delete specified subtasks from Redis (simulate they were removed)
    deleted_task_ids = []
    for idx in tasks_to_delete_indices:
        await task_signatures[idx].delete()
        deleted_task_ids.append(task_signatures[idx].key)

    # Act
    await swarm_signature.safe_change_status(swarm_signature.key, new_status)

    # Assert
    # Verify swarm signature status changed to new status
    reloaded_swarm = await TaskSignature.get_safe(swarm_signature.key)
    assert reloaded_swarm.task_status.status == new_status
    assert reloaded_swarm.task_status.last_status == SignatureStatus.PENDING

    # Verify deleted sub-tasks are still deleted
    await assert_tasks_not_exists(deleted_task_ids)

    # Verify non-deleted subtasks changed status to new status
    non_deleted_indices = [
        task_signatures[i].key
        for i in range(len(task_signatures))
        if i not in tasks_to_delete_indices
    ]
    await assert_tasks_changed_status(
        non_deleted_indices, new_status, SignatureStatus.PENDING
    )
    batch_non_deleted_tasks = [
        swarm_signature.tasks[i]
        for i in range(len(task_signatures))
        if i not in tasks_to_delete_indices
    ]
    await assert_tasks_changed_status(
        non_deleted_indices, new_status, SignatureStatus.PENDING
    )

    # Verify no Redis keys contain the deleted subtask IDs
    await assert_redis_keys_do_not_contain_sub_task_ids(redis_client, deleted_task_ids)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [SignatureStatus.CANCELED],
)
async def test_add_task_raises_runtime_error_when_swarm_not_active_edge_case(
    status: SignatureStatus,
):
    # Arrange
    task_signature = await mageflow.sign(
        "test_task", model_validators=ContextMessage
    )

    swarm_signature = await mageflow.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
    )
    swarm_signature.task_status.status = status
    await swarm_signature.asave()

    # Act & Assert
    with pytest.raises(RuntimeError):
        await swarm_signature.add_task(task_signature)


@pytest.mark.asyncio
async def test_swarm_safe_change_status_on_deleted_signature_does_not_create_redis_entry_sanity():
    # Arrange
    # Create a swarm but then delete it to simulate an unsaved/deleted state
    swarm_signature = await mageflow.swarm(
        task_name="test_swarm_unsaved",
        kwargs={},
        model_validators=ContextMessage,
    )
    # Store the key before deleting
    swarm_key = swarm_signature.key
    await swarm_signature.delete()

    # Act
    result = await SwarmTaskSignature.safe_change_status(
        swarm_key, SignatureStatus.SUSPENDED
    )

    # Assert
    assert result is False
    reloaded_signature = await TaskSignature.get_safe(swarm_key)
    assert reloaded_signature is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["last_status"],
    [
        [SignatureStatus.ACTIVE],
        [SignatureStatus.PENDING],
        [SignatureStatus.PENDING],
    ],
)
async def test_swarm_resume_with_status_changes_sanity(
    mock_aio_run_no_wait, swarm_with_tasks, last_status
):
    # Arrange
    initial_status = SignatureStatus.SUSPENDED
    swarm_data = swarm_with_tasks

    # Set statuses based on the parameter
    for task_signature in swarm_data.task_signatures:
        task_signature.task_status.status = initial_status
        task_signature.task_status.last_status = last_status
        await task_signature.asave()

    swarm_data.swarm_signature.task_status.status = initial_status
    swarm_data.swarm_signature.task_status.last_status = last_status
    await swarm_data.swarm_signature.asave()

    # Act
    await swarm_data.swarm_signature.resume()

    # Assert
    await assert_tasks_changed_status([swarm_data.swarm_signature.key], last_status)

    # Check that original tasks' status changed
    task_ids = [task.key for task in swarm_data.task_signatures]
    task_status = (
        last_status
        if last_status != SignatureStatus.ACTIVE
        else SignatureStatus.PENDING
    )
    await assert_tasks_changed_status(task_ids, task_status, initial_status)


@pytest.mark.asyncio
async def test_swarm_suspend_sanity(swarm_with_tasks):
    # Arrange
    swarm_data = swarm_with_tasks

    # Act
    await swarm_data.swarm_signature.suspend()

    # Assert
    # Verify all tasks changed status to suspend
    await assert_tasks_changed_status(
        swarm_data.swarm_signature, SignatureStatus.SUSPENDED
    )
    await assert_tasks_changed_status(
        swarm_data.swarm_signature.tasks, SignatureStatus.SUSPENDED
    )
    await assert_tasks_changed_status(
        swarm_data.task_signatures, SignatureStatus.SUSPENDED
    )
