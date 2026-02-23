import pytest

import thirdmagic
from thirdmagic.swarm.model import SwarmConfig


@pytest.mark.asyncio
async def test_add_task_reaches_max_and_closes_swarm(mock_close_swarm, mock_task_def):
    # Arrange
    swarm_signature = await thirdmagic.swarm(
        task_name="test_swarm",
        config=SwarmConfig(max_task_allowed=2),
    )

    task_signature_1 = await thirdmagic.sign("test_task_1")
    task_signature_2 = await thirdmagic.sign("test_task_2")

    # Act
    mock_close_swarm.return_value = swarm_signature
    await swarm_signature.add_task(task_signature_1, close_on_max_task=True)
    await swarm_signature.add_task(task_signature_2, close_on_max_task=True)

    # Assert
    mock_close_swarm.assert_called_once_with()


@pytest.mark.asyncio
async def test_add_task_not_reaching_max(mock_close_swarm, test_task_def):
    # Arrange
    swarm_signature = await thirdmagic.swarm(
        task_name="test_swarm",
        config=SwarmConfig(max_task_allowed=3),
    )

    task_signature = await thirdmagic.sign("test_task")

    # Act
    await swarm_signature.add_task(task_signature, close_on_max_task=True)

    # Assert
    mock_close_swarm.assert_not_called()


@pytest.mark.asyncio
async def test_add_task_reaches_max_but_no_close(mock_close_swarm, mock_task_def):
    # Arrange
    swarm_signature = await thirdmagic.swarm(
        task_name="test_swarm",
        config=SwarmConfig(max_task_allowed=2),
    )

    task_signature_1 = await thirdmagic.sign("test_task_1")
    task_signature_2 = await thirdmagic.sign("test_task_2")

    # Act
    await swarm_signature.add_task(task_signature_1, close_on_max_task=False)
    await swarm_signature.add_task(task_signature_2, close_on_max_task=False)

    # Assert
    mock_close_swarm.assert_not_called()
