import pytest

import mageflow
from mageflow.config import SignatureTTLConfig, TTLConfig, apply_ttl_config
from tests.integration.hatchet.models import ContextMessage
from tests.unit.assertions import assert_task_has_done_ttl

TASK_DONE_TTL = 50
CHAIN_DONE_TTL = 80
SWARM_DONE_TTL = 120


@pytest.fixture(autouse=True)
def _apply_ttl():
    apply_ttl_config(
        TTLConfig(
            task=SignatureTTLConfig(ttl_when_sign_done=TASK_DONE_TTL),
            chain=SignatureTTLConfig(ttl_when_sign_done=CHAIN_DONE_TTL),
            swarm=SignatureTTLConfig(ttl_when_sign_done=SWARM_DONE_TTL),
        )
    )


@pytest.mark.asyncio
async def test_task_signature_remove_sets_done_ttl(redis_client, mock_task_def):
    signature = await mageflow.asign("test_task", model_validators=ContextMessage)

    await signature.remove()

    await assert_task_has_done_ttl(redis_client, signature.key, TASK_DONE_TTL)


@pytest.mark.asyncio
async def test_chain_signature_remove_sets_done_ttl(redis_client):
    task_sigs = [
        await mageflow.asign(f"chain_task_{i}", model_validators=ContextMessage)
        for i in range(2)
    ]
    chain_sig = await mageflow.achain([t.key for t in task_sigs])

    await chain_sig.remove()

    await assert_task_has_done_ttl(redis_client, chain_sig.key, CHAIN_DONE_TTL)
    for task in task_sigs:
        await assert_task_has_done_ttl(redis_client, task.key, TASK_DONE_TTL)


@pytest.mark.asyncio
async def test_swarm_signature_remove_sets_done_ttl(redis_client, mock_task_def):
    swarm_sig = await mageflow.aswarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        is_swarm_closed=True,
    )
    task_sigs = [await mageflow.asign(f"swarm_item_{i}") for i in range(2)]
    for task in task_sigs:
        await swarm_sig.add_task(task)

    await swarm_sig.remove()

    await assert_task_has_done_ttl(redis_client, swarm_sig.key, SWARM_DONE_TTL)
    for task in task_sigs:
        await assert_task_has_done_ttl(redis_client, task.key, TASK_DONE_TTL)
