import asyncio
import json

import pytest
from thirdmagic.task import TaskSignature

from tests.integration.hatchet.assertions import get_runs, map_wf_by_external_id
from tests.integration.hatchet.conftest import HatchetInitData
from tests.integration.hatchet.models import ContextMessage
from tests.integration.hatchet.worker import retry_cache_durable_task


@pytest.mark.asyncio(loop_scope="session")
async def test__retry_cache__durable_task_retry__no_duplicate_signatures(
    hatchet_client_init: HatchetInitData,
    test_ctx,
    ctx_metadata,
    trigger_options,
):
    """Test that when a durable task fails and retries, the retry cache ensures
    signatures created on the first attempt are reused on the retry attempt,
    preventing duplicate signatures."""
    # Arrange
    redis_client, hatchet = (
        hatchet_client_init.redis_client,
        hatchet_client_init.hatchet,
    )

    signature = await hatchet.asign(retry_cache_durable_task)
    msg = ContextMessage(base_data=test_ctx)

    # Act - trigger the durable task which will fail on attempt 1 and succeed on attempt 2
    ref = await signature.aio_run_no_wait(msg, options=trigger_options)

    # Wait for the task to complete (it retries once)
    await asyncio.sleep(30)

    # Get the workflow run to find its ID
    runs = await get_runs(hatchet, ctx_metadata)
    runs_by_ext_id = map_wf_by_external_id(runs)

    # Find the workflow run for our task
    workflow_run = runs_by_ext_id.get(ref.workflow_run_id)
    assert workflow_run is not None, "Workflow run not found"

    workflow_id = workflow_run.task_external_id

    # Assert - get the keys stored by each attempt from Redis
    attempt_1_raw = await TaskSignature.Meta.redis.get(
        f"retry-cache-test:{workflow_id}:attempt-1"
    )
    attempt_2_raw = await TaskSignature.Meta.redis.get(
        f"retry-cache-test:{workflow_id}:attempt-2"
    )

    assert attempt_1_raw is not None, "Attempt 1 keys not found in Redis"
    assert attempt_2_raw is not None, "Attempt 2 keys not found in Redis"

    attempt_1_keys = json.loads(attempt_1_raw)
    attempt_2_keys = json.loads(attempt_2_raw)

    # Verify all signature keys are identical between attempts
    assert attempt_1_keys["sig1"] == attempt_2_keys["sig1"], (
        f"sig1 mismatch: {attempt_1_keys['sig1']} != {attempt_2_keys['sig1']}"
    )
    assert attempt_1_keys["sig2"] == attempt_2_keys["sig2"], (
        f"sig2 mismatch: {attempt_1_keys['sig2']} != {attempt_2_keys['sig2']}"
    )
    assert attempt_1_keys["chain_key"] == attempt_2_keys["chain_key"], (
        f"chain_key mismatch: {attempt_1_keys['chain_key']} != {attempt_2_keys['chain_key']}"
    )
    assert attempt_1_keys["chain_sub1"] == attempt_2_keys["chain_sub1"], (
        f"chain_sub1 mismatch"
    )
    assert attempt_1_keys["chain_sub2"] == attempt_2_keys["chain_sub2"], (
        f"chain_sub2 mismatch"
    )
    assert attempt_1_keys["swarm_key"] == attempt_2_keys["swarm_key"], (
        f"swarm_key mismatch: {attempt_1_keys['swarm_key']} != {attempt_2_keys['swarm_key']}"
    )
    assert attempt_1_keys["swarm_sub1"] == attempt_2_keys["swarm_sub1"], (
        f"swarm_sub1 mismatch"
    )
    assert attempt_1_keys["swarm_sub2"] == attempt_2_keys["swarm_sub2"], (
        f"swarm_sub2 mismatch"
    )
