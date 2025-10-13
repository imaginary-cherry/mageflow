import pytest

import orchestrator
from orchestrator import TaskSignature, CommandTaskMessage
from orchestrator.hatchet.config import orchestrator_config
from orchestrator.hatchet.signature import SignatureStatus
from orchestrator.hatchet.swarm import SwarmTaskSignature
from orchestrator.initialization import update_register_signature_models
from tests.unit.hatchet.conftest import assert_redis_keys_do_not_contain_sub_task_ids


@pytest.mark.asyncio
async def test_swarm_stop_signature_changes_all_swarm_and_chain_tasks_status_to_stopped_sanity(
    redis_client, hatchet_mock
):
    # Arrange
    orchestrator_config.redis_client = redis_client
    orchestrator_config.hatchet_client = hatchet_mock

    # Register signature models so TaskSignature.from_id works correctly
    update_register_signature_models()

    # Create individual task signatures for chain
    chain_task_signature_1 = TaskSignature(
        task_name="chain_task_1",
        kwargs={},
        model_validators=CommandTaskMessage,
    )
    await chain_task_signature_1.save()

    chain_task_signature_2 = TaskSignature(
        task_name="chain_task_2",
        kwargs={},
        model_validators=CommandTaskMessage,
    )
    await chain_task_signature_2.save()

    chain_task_signature_3 = TaskSignature(
        task_name="chain_task_3",
        kwargs={},
        model_validators=CommandTaskMessage,
    )
    await chain_task_signature_3.save()

    # Create chain from the individual tasks
    chain_signature = await orchestrator.chain(
        [
            chain_task_signature_1.id,
            chain_task_signature_2.id,
            chain_task_signature_3.id,
        ]
    )

    # Create additional swarm task signatures (not part of chain)
    swarm_task_signature_1 = TaskSignature(
        task_name="swarm_task_1",
        kwargs={},
        model_validators=CommandTaskMessage,
    )
    await swarm_task_signature_1.save()

    swarm_task_signature_2 = TaskSignature(
        task_name="swarm_task_2",
        kwargs={},
        model_validators=CommandTaskMessage,
    )
    await swarm_task_signature_2.save()

    # Create swarm with both chain and individual tasks
    swarm_signature = SwarmTaskSignature(
        task_name="test_swarm",
        kwargs={},
        model_validators=CommandTaskMessage,
        tasks=[
            chain_signature.id,
            swarm_task_signature_1.id,
            swarm_task_signature_2.id,
        ],
    )
    await swarm_signature.save()
    expected_stopped_tasks = [
        swarm_signature,
        chain_signature,
        swarm_task_signature_1,
        swarm_task_signature_2,
        chain_task_signature_1,
        chain_task_signature_2,
        chain_task_signature_3,
    ]

    # Act
    await swarm_signature.change_status(SignatureStatus.STOPPED)

    # Assert
    # Verify swarm signature status changed to stopped
    for task in expected_stopped_tasks:
        updated_signature = await TaskSignature.from_id(task.id)
        assert (
            updated_signature.status == SignatureStatus.STOPPED
        ), f"{task.id} not stopped - {task.task_name}"


@pytest.mark.asyncio
async def test_swarm_stop_signature_with_deleted_sub_tasks_does_not_change_status_edge_case(
    redis_client, hatchet_mock
):
    # Arrange
    orchestrator_config.redis_client = redis_client
    orchestrator_config.hatchet_client = hatchet_mock

    # Register signature models so TaskSignature.from_id works correctly
    update_register_signature_models()

    # Create swarm task signatures
    swarm_task_signature_1 = TaskSignature(
        task_name="swarm_task_1",
        kwargs={},
        model_validators=CommandTaskMessage,
    )
    await swarm_task_signature_1.save()

    swarm_task_signature_2 = TaskSignature(
        task_name="swarm_task_2",
        kwargs={},
        model_validators=CommandTaskMessage,
    )
    await swarm_task_signature_2.save()

    # Create swarm with task signatures
    swarm_signature = SwarmTaskSignature(
        task_name="test_swarm",
        kwargs={},
        model_validators=CommandTaskMessage,
        tasks=[swarm_task_signature_1.id, swarm_task_signature_2.id],
    )
    await swarm_signature.save()

    # Delete sub-tasks from Redis (simulate they were removed)
    await swarm_task_signature_1.remove()
    await swarm_task_signature_2.remove()

    # Act
    await swarm_signature.change_status(SignatureStatus.STOPPED)

    # Assert
    # Verify swarm signature status changed to stopped
    reloaded_swarm = await TaskSignature.from_id(swarm_signature.id)
    assert reloaded_swarm.status == SignatureStatus.STOPPED

    # Verify no Redis keys contain the deleted sub-task IDs
    await assert_redis_keys_do_not_contain_sub_task_ids(
        redis_client, [swarm_task_signature_1.id, swarm_task_signature_2.id]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "task_ids", [["task_1"], ["task_1", "task_2"], ["task_1", "task_2", "task_3"]]
)
async def test_add_to_finished_tasks_sanity(redis_client, hatchet_mock, task_ids):
    # Arrange
    orchestrator_config.redis_client = redis_client
    orchestrator_config.hatchet_client = hatchet_mock
    update_register_signature_models()

    swarm_signature = SwarmTaskSignature(
        task_name="test_swarm",
        kwargs={},
        model_validators=CommandTaskMessage,
        finished_tasks=[],
    )
    await swarm_signature.save()
    original_finished_tasks = swarm_signature.finished_tasks.copy()

    # Act
    for task_id in task_ids:
        await swarm_signature.add_to_finished_tasks(task_id)

    # Assert
    reloaded_swarm = await SwarmTaskSignature.from_id(swarm_signature.id)
    finished_tasks = original_finished_tasks + task_ids
    assert reloaded_swarm.finished_tasks == finished_tasks
    assert swarm_signature.finished_tasks == finished_tasks


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "task_ids", [["task_1"], ["task_1", "task_2"], ["task_1", "task_2", "task_3"]]
)
async def test_add_to_failed_tasks_sanity(redis_client, hatchet_mock, task_ids):
    # Arrange
    orchestrator_config.redis_client = redis_client
    orchestrator_config.hatchet_client = hatchet_mock
    update_register_signature_models()

    swarm_signature = SwarmTaskSignature(
        task_name="test_swarm",
        kwargs={},
        model_validators=CommandTaskMessage,
        failed_tasks=[],
    )
    await swarm_signature.save()
    original_failed_tasks = swarm_signature.failed_tasks.copy()

    # Act
    for task_id in task_ids:
        await swarm_signature.add_to_failed_tasks(task_id)

    # Assert
    reloaded_swarm = await SwarmTaskSignature.from_id(swarm_signature.id)
    failed_tasks = original_failed_tasks + task_ids
    assert reloaded_swarm.failed_tasks == failed_tasks
    assert swarm_signature.failed_tasks == failed_tasks


@pytest.mark.asyncio
@pytest.mark.parametrize("initial_count,decrease_amount", [[5, 1], [10, 1], [3, 1]])
async def test_decrease_running_tasks_count_sanity(
    redis_client, hatchet_mock, initial_count, decrease_amount
):
    # Arrange
    orchestrator_config.redis_client = redis_client
    orchestrator_config.hatchet_client = hatchet_mock
    update_register_signature_models()

    swarm_signature = SwarmTaskSignature(
        task_name="test_swarm",
        kwargs={},
        model_validators=CommandTaskMessage,
        current_running_tasks=initial_count,
    )
    await swarm_signature.save()
    original_running_tasks = swarm_signature.current_running_tasks

    # Act
    await swarm_signature.decrease_running_tasks_count()

    # Assert
    reloaded_swarm = await SwarmTaskSignature.from_id(swarm_signature.id)
    final_count = initial_count - decrease_amount
    assert reloaded_swarm.current_running_tasks == final_count
    assert swarm_signature.current_running_tasks == final_count


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "max_concurrency,current_running,expected_can_run",
    [[5, 3, True], [5, 4, True], [5, 5, False], [1, 1, False], [10, 0, True]],
)
async def test_add_to_running_tasks_sanity(
    redis_client, hatchet_mock, max_concurrency, current_running, expected_can_run
):
    # Arrange
    orchestrator_config.redis_client = redis_client
    orchestrator_config.hatchet_client = hatchet_mock
    update_register_signature_models()

    from orchestrator.hatchet.swarm import SwarmConfig

    task_signature = TaskSignature(
        task_name="test_task",
        kwargs={},
        model_validators=CommandTaskMessage,
    )
    await task_signature.save()

    swarm_signature = SwarmTaskSignature(
        task_name="test_swarm",
        kwargs={},
        model_validators=CommandTaskMessage,
        current_running_tasks=current_running,
        config=SwarmConfig(max_concurrency=max_concurrency),
        tasks_left_to_run=[],
    )
    await swarm_signature.save()
    original_running_tasks = swarm_signature.current_running_tasks
    original_tasks_left_to_run = swarm_signature.tasks_left_to_run.copy()

    # Act
    can_run = await swarm_signature.add_to_running_tasks(task_signature)

    # Assert
    reloaded_swarm = await SwarmTaskSignature.from_id(swarm_signature.id)
    assert can_run == expected_can_run

    if expected_can_run:
        assert reloaded_swarm.current_running_tasks == current_running + 1
        assert reloaded_swarm.tasks_left_to_run == original_tasks_left_to_run
    else:
        assert reloaded_swarm.current_running_tasks == current_running
        assert reloaded_swarm.tasks_left_to_run == original_tasks_left_to_run + [
            task_signature.id
        ]

    assert swarm_signature.current_running_tasks == original_running_tasks
    assert swarm_signature.tasks_left_to_run == original_tasks_left_to_run


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "initial_tasks",
    [["task_1"], ["task_1", "task_2"], ["task_1", "task_2", "task_3"], []],
)
async def test_pop_task_to_run_sanity(redis_client, hatchet_mock, initial_tasks):
    # Arrange
    orchestrator_config.redis_client = redis_client
    orchestrator_config.hatchet_client = hatchet_mock
    update_register_signature_models()

    swarm_signature = SwarmTaskSignature(
        task_name="test_swarm",
        kwargs={},
        model_validators=CommandTaskMessage,
        tasks_left_to_run=initial_tasks.copy(),
    )
    await swarm_signature.save()
    original_tasks_left_to_run = swarm_signature.tasks_left_to_run.copy()

    # Act
    popped_task = await swarm_signature.pop_task_to_run()

    # Assert
    reloaded_swarm = await SwarmTaskSignature.from_id(swarm_signature.id)

    if initial_tasks:
        expected_popped = initial_tasks[0]
        expected_remaining = initial_tasks[1:]
        assert popped_task == expected_popped
        assert reloaded_swarm.tasks_left_to_run == expected_remaining
    else:
        assert popped_task is None
        assert reloaded_swarm.tasks_left_to_run == []

    assert swarm_signature.tasks_left_to_run == original_tasks_left_to_run
