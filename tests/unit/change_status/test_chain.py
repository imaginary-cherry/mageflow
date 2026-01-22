from dataclasses import dataclass

import pytest

import mageflow
from mageflow.chain.model import ChainTaskSignature
from mageflow.signature.model import TaskSignature
from mageflow.signature.status import SignatureStatus
from tests.integration.hatchet.models import ContextMessage
from tests.unit.assertions import assert_redis_keys_do_not_contain_sub_task_ids
from tests.unit.assertions import (
    assert_tasks_not_exists,
    assert_tasks_changed_status,
)


@dataclass
class TaskResumeConfig:
    name: str
    last_status: SignatureStatus


@pytest.mark.asyncio
async def test_chain_safe_change_status_on_unsaved_signature_does_not_create_redis_entry_sanity():
    # Arrange
    chain_signature = ChainTaskSignature(
        task_name="test_chain_unsaved",
        kwargs={},
        model_validators=ContextMessage,
        tasks=["task_1", "task_2", "task_3"],
    )

    # Act
    result = await ChainTaskSignature.safe_change_status(
        chain_signature.key, SignatureStatus.SUSPENDED
    )

    # Assert
    assert result is False
    reloaded_signature = await TaskSignature.get_safe(chain_signature.key)
    assert reloaded_signature is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["task_names", "tasks_to_delete_indices", "new_status"],
    [
        [
            ["task1", "task2", "task3"],
            [],
            SignatureStatus.SUSPENDED,
        ],
        [
            ["task1", "task2"],
            [0, 1],
            SignatureStatus.CANCELED,
        ],
        [
            ["task1", "task2", "task3"],
            [0, 2],
            SignatureStatus.ACTIVE,
        ],
    ],
)
async def test_chain_change_status_with_optional_deleted_sub_tasks_edge_case(
    redis_client,
    task_names: list[str],
    tasks_to_delete_indices: list[int],
    new_status: SignatureStatus,
):
    # Arrange
    # Create task signatures via API
    task_signatures = [await mageflow.sign(name) for name in task_names]

    # Create a chain
    chain_signature = await mageflow.chain([task.key for task in task_signatures])

    # Delete specified subtasks from Redis (simulate they were removed)
    deleted_task_ids = []
    for idx in tasks_to_delete_indices:
        await task_signatures[idx].adelete()
        deleted_task_ids.append(task_signatures[idx].key)

    # Act
    await chain_signature.safe_change_status(chain_signature.key, new_status)

    # Assert
    # Verify chain signature status changed to new status
    reloaded_chain = await TaskSignature.get_safe(chain_signature.key)
    assert reloaded_chain.task_status.status == new_status
    assert reloaded_chain.task_status.last_status == SignatureStatus.PENDING

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

    # Verify no Redis keys contain the deleted subtask IDs
    await assert_redis_keys_do_not_contain_sub_task_ids(redis_client, deleted_task_ids)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["task_configs", "tasks_to_delete_indices"],
    [
        [
            [
                TaskResumeConfig(name="task1", last_status=SignatureStatus.ACTIVE),
                TaskResumeConfig(name="task2", last_status=SignatureStatus.ACTIVE),
                TaskResumeConfig(name="task3", last_status=SignatureStatus.ACTIVE),
            ],
            [],
        ],
        [
            [
                TaskResumeConfig(name="task1", last_status=SignatureStatus.PENDING),
                TaskResumeConfig(name="task2", last_status=SignatureStatus.PENDING),
            ],
            [0],
        ],
        [
            [
                TaskResumeConfig(name="task1", last_status=SignatureStatus.ACTIVE),
                TaskResumeConfig(name="task2", last_status=SignatureStatus.ACTIVE),
                TaskResumeConfig(name="task3", last_status=SignatureStatus.ACTIVE),
            ],
            [1, 2],
        ],
    ],
)
async def test_chain_resume_with_optional_deleted_sub_tasks_sanity(
    mock_aio_run_no_wait,
    task_configs: list[TaskResumeConfig],
    tasks_to_delete_indices: list[int],
):
    # Arrange
    task_signatures = []
    expected_statuses = []
    num_of_aio_run = 0
    for config in task_configs:
        task_signature = await mageflow.sign(config.name)
        task_signature.task_status.status = SignatureStatus.SUSPENDED
        task_signature.task_status.last_status = config.last_status
        await task_signature.asave()
        task_signatures.append(task_signature)
        expected_statuses.append(config.last_status)

    chain_signature = await mageflow.chain([task.key for task in task_signatures])
    chain_signature.task_status.status = SignatureStatus.SUSPENDED

    deleted_task_ids = []
    for idx in tasks_to_delete_indices:
        await task_signatures[idx].adelete()
        deleted_task_ids.append(task_signatures[idx].key)

    # Act
    await chain_signature.resume()

    # Assert
    non_deleted_task_ids = [
        i for i in range(len(task_signatures)) if i not in tasks_to_delete_indices
    ]
    for i in non_deleted_task_ids:
        task = task_signatures[i]
        new_status = expected_statuses[i]
        if new_status == SignatureStatus.ACTIVE:
            new_status = SignatureStatus.PENDING
            num_of_aio_run += 1
        await assert_tasks_changed_status(
            [task.key], new_status, SignatureStatus.SUSPENDED
        )

    await assert_tasks_changed_status(
        [chain_signature.key], SignatureStatus.PENDING, SignatureStatus.SUSPENDED
    )

    await assert_tasks_not_exists(deleted_task_ids)
    assert mock_aio_run_no_wait.call_count == num_of_aio_run


@pytest.mark.asyncio
async def test_chain_suspend_sanity(chain_with_tasks):
    # Arrange
    chain_data = chain_with_tasks

    # Act
    await chain_data.chain_signature.suspend()

    # Assert
    # Verify all tasks changed status to suspend
    await assert_tasks_changed_status(
        [chain_data.chain_signature.key], SignatureStatus.SUSPENDED
    )
    await assert_tasks_changed_status(
        [task.key for task in chain_data.task_signatures], SignatureStatus.SUSPENDED
    )
