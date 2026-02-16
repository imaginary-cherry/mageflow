import pytest

import mageflow
from mageflow.startup import init_mageflow


@pytest.fixture
def dummy_task():
    task_name = "dummy_ttl_test_task"
    return task_name


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize(
    ["entity_type"],
    [
        ["signature"],
        ["chain"],
        ["swarm"],
    ],
)
async def test_redis_ttl_verification_sanity(real_redis, dummy_task, entity_type):
    # Arrange
    redis_client = real_redis
    await init_mageflow(redis_client)

    expected_ttl = 24 * 60 * 60  # 1 day in seconds
    ttl_tolerance = 100  # seconds tolerance for test execution time

    # Act
    if entity_type == "signature":
        entity = await mageflow.asign(dummy_task)
        key = entity.key
    elif entity_type == "chain":
        sig1 = await mageflow.asign(dummy_task, step=1)
        sig2 = await mageflow.asign(dummy_task, step=2)
        entity = await mageflow.achain([sig1, sig2], name="test_chain")
        key = entity.key
    elif entity_type == "swarm":
        sig1 = await mageflow.asign(dummy_task, worker=1)
        sig2 = await mageflow.asign(dummy_task, worker=2)
        entity = await mageflow.aswarm([sig1, sig2], task_name="test_swarm")
        key = entity.key
    else:
        raise ValueError(f"Unknown entity type: {entity_type}")

    ttl_result = await redis_client.ttl(key)

    # Assert
    assert (
        ttl_result > expected_ttl - ttl_tolerance
    ), f"TTL for {entity_type} is too low: {ttl_result}"
    assert (
        ttl_result <= expected_ttl
    ), f"TTL for {entity_type} is too high: {ttl_result}"
