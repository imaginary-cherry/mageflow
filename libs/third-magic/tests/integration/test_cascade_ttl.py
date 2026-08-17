import pytest
from pydantic import BaseModel

import thirdmagic

SHORT_TTL = 100
ACTIVE_TTL = 24 * 60 * 60


class Msg(BaseModel):
    x: int = 0


@pytest.mark.asyncio(loop_scope="session")
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


@pytest.mark.asyncio(loop_scope="session")
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


@pytest.mark.asyncio(loop_scope="session")
async def test_swarm_write_cascades_ttl_to_a_nested_chain(real_redis, mock_adapter):
    # Arrange: a swarm whose sub-task is itself a container, not a plain TaskSignature
    inner_tasks = [
        await thirdmagic.sign(f"nested_chain_task_{i}", model_validators=Msg)
        for i in range(2)
    ]
    inner_chain = await thirdmagic.chain([task.key for task in inner_tasks])
    swarm = await thirdmagic.swarm(task_name="cascade_swarm_of_chain")
    await swarm.add_tasks([inner_chain])
    await real_redis.expire(inner_chain.key, SHORT_TTL)

    # Act
    await swarm.close_swarm(should_check_swarm=False)

    # Assert
    assert await real_redis.ttl(inner_chain.key) > SHORT_TTL


@pytest.mark.asyncio(loop_scope="session")
async def test_swarm_write_cascades_ttl_through_a_nested_chain_to_its_own_tasks(
    real_redis, mock_adapter
):
    # Arrange: the cascade must recurse past the resolved container into its leaves
    inner_tasks = [
        await thirdmagic.sign(f"deep_chain_task_{i}", model_validators=Msg)
        for i in range(2)
    ]
    inner_chain = await thirdmagic.chain([task.key for task in inner_tasks])
    swarm = await thirdmagic.swarm(task_name="cascade_swarm_deep")
    await swarm.add_tasks([inner_chain])
    for task in inner_tasks:
        await real_redis.expire(task.key, SHORT_TTL)

    # Act
    await swarm.close_swarm(should_check_swarm=False)

    # Assert
    for task in inner_tasks:
        assert await real_redis.ttl(task.key) > SHORT_TTL


@pytest.mark.asyncio(loop_scope="session")
async def test_swarm_write_cascades_ttl_to_a_nested_swarm(real_redis, mock_adapter):
    # Arrange: same-class nesting resolves through the candidate list too
    inner_swarm = await thirdmagic.swarm(task_name="cascade_inner_swarm")
    outer_swarm = await thirdmagic.swarm(task_name="cascade_outer_swarm")
    await outer_swarm.add_tasks([inner_swarm])
    await real_redis.expire(inner_swarm.key, SHORT_TTL)

    # Act
    await outer_swarm.close_swarm(should_check_swarm=False)

    # Assert
    assert await real_redis.ttl(inner_swarm.key) > SHORT_TTL


@pytest.mark.asyncio(loop_scope="session")
async def test_chain_write_cascades_ttl_to_a_nested_swarm(real_redis, mock_adapter):
    # Arrange: the chain edge resolves multi-class the same way the swarm edge does
    inner_swarm = await thirdmagic.swarm(task_name="cascade_chain_inner_swarm")
    plain_task = await thirdmagic.sign("cascade_chain_plain", model_validators=Msg)
    chain = await thirdmagic.chain([inner_swarm, plain_task])
    await real_redis.expire(inner_swarm.key, SHORT_TTL)

    # Act
    await chain.aupdate(task_name=chain.task_name)

    # Assert
    assert await real_redis.ttl(inner_swarm.key) > SHORT_TTL
