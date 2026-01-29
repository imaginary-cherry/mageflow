import pytest

import mageflow
from mageflow.errors import TooManyTasksError
from mageflow.swarm.model import SwarmConfig
from tests.integration.hatchet.models import ContextMessage


@pytest.mark.asyncio
@pytest.mark.parametrize(["max_task_allowed"], [[2], [1], [5]])
async def test_add_task_exceeds_max_task_allowed_error(max_task_allowed):
    # Arrange
    initial_tasks = [
        await mageflow.sign(f"test_task_{i}") for i in range(max_task_allowed)
    ]
    swarm_signature = await mageflow.swarm(
        task_name="test_swarm",
        tasks=initial_tasks,
        model_validators=ContextMessage,
        config=SwarmConfig(max_task_allowed=max_task_allowed),
    )

    # Act & Assert
    extra_task = await mageflow.sign("test_task_last")
    with pytest.raises(TooManyTasksError):
        await swarm_signature.add_task(extra_task)
