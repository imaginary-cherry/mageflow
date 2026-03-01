import pytest

from tests.integration.hatchet.conftest import HatchetInitData
from tests.integration.hatchet.models import ContextMessage, SignatureKeysResult
from tests.integration.hatchet.worker import (
    create_signatures_for_ttl_test,
    TASK_ACTIVE_TTL,
    CHAIN_ACTIVE_TTL,
    SWARM_ACTIVE_TTL,
)

TTL_TOLERANCE = 60  # seconds


async def assert_ttl_in_range(redis_client, key, expected_ttl, label):
    actual_ttl = await redis_client.ttl(key)
    assert actual_ttl > expected_ttl - TTL_TOLERANCE, (
        f"{label} key {key}: TTL {actual_ttl}s below minimum (expected ~{expected_ttl}s)"
    )
    assert actual_ttl <= expected_ttl, (
        f"{label} key {key}: TTL {actual_ttl}s exceeds {expected_ttl}s"
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_signature_ttl_matches_config(hatchet_client_init: HatchetInitData, test_ctx):
    redis_client = hatchet_client_init.redis_client
    message = ContextMessage(base_data=test_ctx)

    # Call task and wait for completion
    result = await create_signatures_for_ttl_test.aio_run(message)
    output = SignatureKeysResult(**list(result.values())[0])

    # Check TaskSignature keys -> TASK_ACTIVE_TTL
    for key in output.task_keys:
        await assert_ttl_in_range(redis_client, key, TASK_ACTIVE_TTL, "TaskSignature")

    # Check ChainTaskSignature -> CHAIN_ACTIVE_TTL
    await assert_ttl_in_range(redis_client, output.chain_key, CHAIN_ACTIVE_TTL, "ChainTaskSignature")

    # Check chain sub-tasks (TaskSignatures) -> TASK_ACTIVE_TTL
    for key in output.chain_sub_task_keys:
        await assert_ttl_in_range(redis_client, key, TASK_ACTIVE_TTL, "Chain sub-TaskSignature")

    # Check SwarmTaskSignature -> SWARM_ACTIVE_TTL
    await assert_ttl_in_range(redis_client, output.swarm_key, SWARM_ACTIVE_TTL, "SwarmTaskSignature")

    # Check swarm sub-tasks (TaskSignatures) -> TASK_ACTIVE_TTL
    for key in output.swarm_sub_task_keys:
        await assert_ttl_in_range(redis_client, key, TASK_ACTIVE_TTL, "Swarm sub-TaskSignature")

    # Check PublishState -> SWARM_ACTIVE_TTL
    await assert_ttl_in_range(redis_client, output.publish_state_key, SWARM_ACTIVE_TTL, "PublishState")
