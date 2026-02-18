import pytest

import thirdmagic
from tests.unit.assertions import (
    assert_tasks_changed_status,
    assert_tasks_not_exists,
    assert_redis_keys_do_not_contain_sub_task_ids,
)
from tests.unit.change_status.assertions import assert_resume_signature
from tests.unit.change_status.conftest import (
    TaskResumeConfig,
    delete_tasks_by_indices,
    get_non_deleted_task_keys,
)
from tests.unit.messages import ContextMessage
from thirdmagic.chain import ChainTaskSignature
from thirdmagic.task import TaskSignature, SignatureStatus


@pytest.mark.asyncio
async def test_chain_safe_change_status_on_deleted_signature_does_not_create_redis_entry_sanity():
    # Arrange
    task_signatures = [
        await thirdmagic.sign(f"chain_task_{i}", model_validators=ContextMessage)
        for i in range(1, 4)
    ]
    chain_signature = await thirdmagic.chain(
        tasks=task_signatures, name="test_chain_unsaved"
    )
    chain_key = chain_signature.key
    await chain_signature.adelete()

    # Act
    result = await ChainTaskSignature.safe_change_status(
        chain_key, SignatureStatus.SUSPENDED
    )

    # Assert
    assert result is False
    reloaded_signature = await TaskSignature.get_safe(chain_key)
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
    mock_task_def,
):
    # Arrange
    task_signatures = [await thirdmagic.sign(name) for name in task_names]
    chain_signature = await thirdmagic.chain([task.key for task in task_signatures])
    deleted_task_ids = await delete_tasks_by_indices(
        task_signatures, tasks_to_delete_indices
    )

    # Act
    await chain_signature.safe_change_status(chain_signature.key, new_status)

    # Assert
    reloaded_chain = await TaskSignature.get_safe(chain_signature.key)
    assert reloaded_chain.task_status.status == new_status
    assert reloaded_chain.task_status.last_status == SignatureStatus.PENDING

    await assert_tasks_not_exists(deleted_task_ids)

    non_deleted_keys = get_non_deleted_task_keys(
        task_signatures, tasks_to_delete_indices
    )
    await assert_tasks_changed_status(
        non_deleted_keys, new_status, SignatureStatus.PENDING
    )

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
    mock_adapter,
    task_configs: list[TaskResumeConfig],
    tasks_to_delete_indices: list[int],
    mock_task_def,
):
    # Arrange
    task_signatures = []
    expected_statuses = []
    num_of_aio_run = 0
    for config in task_configs:
        task_signature = await thirdmagic.sign(config.name)
        task_signature.task_status.status = SignatureStatus.SUSPENDED
        task_signature.task_status.last_status = config.last_status
        await task_signature.asave()
        task_signatures.append(task_signature)
        expected_statuses.append(config.last_status)

    chain_signature = await thirdmagic.chain([task.key for task in task_signatures])
    chain_signature.task_status.status = SignatureStatus.SUSPENDED

    deleted_task_ids = await delete_tasks_by_indices(
        task_signatures, tasks_to_delete_indices
    )

    # Act
    await chain_signature.resume()

    # Assert
    non_deleted_task_indices = [
        i for i in range(len(task_signatures)) if i not in tasks_to_delete_indices
    ]
    for i in non_deleted_task_indices:
        task = task_signatures[i]
        new_status = expected_statuses[i]
        if new_status == SignatureStatus.ACTIVE:
            new_status = SignatureStatus.PENDING
            assert_resume_signature(task, mock_adapter)
            num_of_aio_run += 1
        await assert_tasks_changed_status(
            [task.key], new_status, SignatureStatus.SUSPENDED
        )

    await assert_tasks_changed_status(
        [chain_signature.key], SignatureStatus.PENDING, SignatureStatus.SUSPENDED
    )

    await assert_tasks_not_exists(deleted_task_ids)
    assert mock_adapter.acall_signature.call_count == num_of_aio_run


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
