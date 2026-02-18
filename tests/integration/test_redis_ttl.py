import pytest
import pytest_asyncio
from thirdmagic.task_def import MageflowTaskDefinition

import mageflow
from mageflow.startup import init_mageflow

TASK_NAME = "dummy_ttl_test_task"
EXPECTED_TTL = 24 * 60 * 60  # 1 day in seconds
TTL_TOLERANCE = 100  # seconds tolerance for test execution time


@pytest_asyncio.fixture(loop_scope="session")
async def mageflow_task_def(real_redis):
    await init_mageflow(real_redis)
    task_def = MageflowTaskDefinition(mageflow_task_name=TASK_NAME, task_name=TASK_NAME)
    await task_def.asave()
    yield task_def


@pytest.mark.asyncio(loop_scope="session")
async def test_signature_redis_ttl(real_redis, mageflow_task_def):
    # Act
    entity = await mageflow.asign(TASK_NAME)
    ttl_result = await real_redis.ttl(entity.key)

    # Assert
    assert (
        ttl_result > EXPECTED_TTL - TTL_TOLERANCE
    ), f"TTL for signature is too low: {ttl_result}"
    assert ttl_result <= EXPECTED_TTL, f"TTL for signature is too high: {ttl_result}"


@pytest.mark.asyncio(loop_scope="session")
async def test_chain_redis_ttl(real_redis, mageflow_task_def):
    # Arrange
    sig1 = await mageflow.asign(TASK_NAME, step=1)
    sig2 = await mageflow.asign(TASK_NAME, step=2)

    # Act
    entity = await mageflow.achain([sig1, sig2], name="test_chain")
    ttl_result = await real_redis.ttl(entity.key)

    # Assert
    assert (
        ttl_result > EXPECTED_TTL - TTL_TOLERANCE
    ), f"TTL for chain is too low: {ttl_result}"
    assert ttl_result <= EXPECTED_TTL, f"TTL for chain is too high: {ttl_result}"


@pytest.mark.asyncio(loop_scope="session")
async def test_swarm_redis_ttl(real_redis, mageflow_task_def):
    # Arrange
    sig1 = await mageflow.asign(TASK_NAME, worker=1)
    sig2 = await mageflow.asign(TASK_NAME, worker=2)

    # Act
    entity = await mageflow.aswarm([sig1, sig2], task_name="test_swarm")
    ttl_result = await real_redis.ttl(entity.key)

    # Assert
    assert (
        ttl_result > EXPECTED_TTL - TTL_TOLERANCE
    ), f"TTL for swarm is too low: {ttl_result}"
    assert ttl_result <= EXPECTED_TTL, f"TTL for swarm is too high: {ttl_result}"
