import pytest
from pydantic import BaseModel

import thirdmagic

SHORT_TTL = 100
ACTIVE_TTL = 24 * 60 * 60


class Msg(BaseModel):
    x: int = 0


@pytest.mark.asyncio
async def test_swarm_write_cascades_ttl_to_sub_tasks(real_redis, mock_adapter):
    # Arrange
    swarm = await thirdmagic.swarm(task_name="cascade_swarm")
    tasks = [
        await thirdmagic.sign(f"cascade_task_{i}", model_validators=Msg)
        for i in range(3)
    ]
    await swarm.add_tasks(tasks)
    for task in tasks:
        await real_redis.expire(task.key, SHORT_TTL)

    # Act: an ordinary write on the swarm refreshes and cascades TTL to its sub-tasks
    await swarm.close_swarm(should_check_swarm=False)

    # Assert
    for task in tasks:
        assert await real_redis.ttl(task.key) > SHORT_TTL


@pytest.mark.asyncio
async def test_chain_write_cascades_ttl_to_sub_tasks(real_redis, mock_adapter):
    # Arrange
    tasks = [
        await thirdmagic.sign(f"cascade_chain_task_{i}", model_validators=Msg)
        for i in range(3)
    ]
    chain = await thirdmagic.chain([task.key for task in tasks])
    for task in tasks:
        await real_redis.expire(task.key, SHORT_TTL)

    # Act: an ordinary write on the chain refreshes and cascades TTL to its sub-tasks
    await chain.aupdate(task_name=chain.task_name)

    # Assert
    for task in tasks:
        assert await real_redis.ttl(task.key) > SHORT_TTL
