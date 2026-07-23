import pytest

import thirdmagic
from thirdmagic.signature.status import SignatureStatus


@pytest.mark.asyncio
async def test_swarm_container_status_terminal_percentage(mock_task_def):
    # Arrange
    swarm = await thirdmagic.swarm(task_name="test_swarm")
    tasks = [await thirdmagic.sign(f"test_task_{i}") for i in range(4)]
    await swarm.add_tasks(tasks)

    async with swarm.apipeline():
        swarm.tasks_left_to_run.remove_range(0, len(swarm.tasks_left_to_run))
        swarm.finished_tasks.append(tasks[0].key)
        swarm.failed_tasks.append(tasks[1].key)
        swarm.current_running_tasks = 1
        swarm.tasks_left_to_run.append(tasks[3].key)

    # Act
    status = await swarm.container_status()

    # Assert
    assert status.signature_id == swarm.key
    assert status.total == 4
    assert status.finished == 1
    assert status.failed == 1
    assert status.running == 1
    assert status.pending == 1
    assert status.percentage == 50.0
    assert status.is_done is False


@pytest.mark.asyncio
async def test_swarm_container_status_done_is_full(mock_task_def):
    # Arrange
    swarm = await thirdmagic.swarm(task_name="test_swarm")
    tasks = [await thirdmagic.sign(f"test_task_{i}") for i in range(2)]
    await swarm.add_tasks(tasks)

    async with swarm.apipeline():
        swarm.tasks_left_to_run.remove_range(0, len(swarm.tasks_left_to_run))
        swarm.finished_tasks.extend([task.key for task in tasks])
        swarm.is_swarm_closed = True

    # Act
    status = await swarm.container_status()

    # Assert
    assert status.percentage == 100.0
    assert status.is_done is True


@pytest.mark.asyncio
async def test_swarm_container_status_empty_is_zero(mock_task_def):
    # Arrange
    swarm = await thirdmagic.swarm(task_name="test_swarm")

    # Act
    status = await swarm.container_status()

    # Assert
    assert status.total == 0
    assert status.percentage == 0.0


@pytest.mark.asyncio
async def test_chain_container_status_classifies_children(mock_task_def):
    # Arrange
    tasks = [await thirdmagic.sign(f"chain_task_{i}") for i in range(4)]
    chain = await thirdmagic.chain([task.key for task in tasks])

    await tasks[0].change_status(SignatureStatus.DONE)
    await tasks[1].change_status(SignatureStatus.FAILED)
    await tasks[2].change_status(SignatureStatus.ACTIVE)
    # tasks[3] stays PENDING

    # Act
    status = await chain.container_status()

    # Assert
    assert status.total == 4
    assert status.finished == 1
    assert status.failed == 1
    assert status.running == 1
    assert status.pending == 1
    assert status.percentage == 50.0
