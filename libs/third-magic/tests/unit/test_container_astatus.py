import pytest

import thirdmagic
from thirdmagic import ContainerStatus
from thirdmagic.signature.status import SignatureStatus


@pytest.mark.asyncio
async def test_swarm_astatus_terminal_percentage(mock_task_def):
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

    expected = ContainerStatus(
        signature_id=swarm.key,
        task_name="test_swarm",
        status=SignatureStatus.PENDING,
        total=4,
        finished=1,
        failed=1,
        running=1,
        pending=1,
        percentage=50.0,
        is_done=False,
    )

    # Act
    status = await swarm.astatus()

    # Assert
    assert status == expected


@pytest.mark.asyncio
async def test_swarm_astatus_done_is_full(mock_task_def):
    # Arrange
    swarm = await thirdmagic.swarm(task_name="test_swarm")
    tasks = [await thirdmagic.sign(f"test_task_{i}") for i in range(2)]
    await swarm.add_tasks(tasks)

    async with swarm.apipeline():
        swarm.tasks_left_to_run.remove_range(0, len(swarm.tasks_left_to_run))
        swarm.finished_tasks.extend([task.key for task in tasks])
        swarm.is_swarm_closed = True

    expected = ContainerStatus(
        signature_id=swarm.key,
        task_name="test_swarm",
        status=SignatureStatus.PENDING,
        total=2,
        finished=2,
        failed=0,
        running=0,
        pending=0,
        percentage=100.0,
        is_done=True,
    )

    # Act
    status = await swarm.astatus()

    # Assert
    assert status == expected


@pytest.mark.asyncio
async def test_swarm_astatus_empty_is_zero(mock_task_def):
    # Arrange
    swarm = await thirdmagic.swarm(task_name="test_swarm")
    expected = ContainerStatus(
        signature_id=swarm.key,
        task_name="test_swarm",
        status=SignatureStatus.PENDING,
        total=0,
        finished=0,
        failed=0,
        running=0,
        pending=0,
        percentage=0.0,
        is_done=False,
    )

    # Act
    status = await swarm.astatus()

    # Assert
    assert status == expected


@pytest.mark.asyncio
async def test_chain_astatus_classifies_children(mock_task_def):
    # Arrange
    tasks = [await thirdmagic.sign(f"chain_task_{i}") for i in range(4)]
    chain = await thirdmagic.chain([task.key for task in tasks])

    await tasks[0].change_status(SignatureStatus.DONE)
    await tasks[1].change_status(SignatureStatus.FAILED)
    await tasks[2].change_status(SignatureStatus.ACTIVE)
    # tasks[3] stays PENDING

    expected = ContainerStatus(
        signature_id=chain.key,
        task_name=chain.task_name,
        status=SignatureStatus.PENDING,
        total=4,
        finished=1,
        failed=1,
        running=1,
        pending=1,
        percentage=50.0,
        is_done=False,
    )

    # Act
    status = await chain.astatus()

    # Assert
    assert status == expected
