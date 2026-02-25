import pytest

import thirdmagic
from tests.unit.messages import ContextMessage
from thirdmagic.errors import TooManyTasksError
from thirdmagic.swarm.model import SwarmConfig


@pytest.mark.asyncio
@pytest.mark.parametrize(["max_task_allowed"], [[2], [1], [5]])
async def test_add_task_exceeds_max_task_allowed_error(mock_task_def, max_task_allowed):
    # Arrange
    initial_tasks = [
        await thirdmagic.sign(f"test_task_{i}") for i in range(max_task_allowed)
    ]
    swarm_signature = await thirdmagic.swarm(
        task_name="test_swarm",
        tasks=initial_tasks,
        model_validators=ContextMessage,
        config=SwarmConfig(max_task_allowed=max_task_allowed),
    )

    # Act & Assert
    extra_task = await thirdmagic.sign("test_task_last")
    with pytest.raises(TooManyTasksError):
        await swarm_signature.add_task(extra_task)
