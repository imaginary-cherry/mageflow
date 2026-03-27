import asyncio

import pytest
from thirdmagic.task import TaskSignature

from tests.integration.hatchet.conftest import HatchetInitData
from tests.integration.hatchet.models import ContextMessage, SignatureKeyWithWF
from tests.integration.hatchet.worker import (
    concurrent_cache_isolation_task,
    retry_cache_durable_task,
)


async def _assert_retry_cache_idempotency(results: SignatureKeyWithWF):
    workflow_run_id = results.workflow_run_id

    # Assert - get the keys stored by each attempt from Redis
    attempt_1_raw = await TaskSignature.Meta.redis.json().get(  # type: ignore[misc]
        f"retry-cache-test:{workflow_run_id}:attempt-1"
    )
    attempt_2_raw = await TaskSignature.Meta.redis.json().get(  # type: ignore[misc]
        f"retry-cache-test:{workflow_run_id}:attempt-2"
    )

    assert attempt_1_raw is not None, "Attempt 1 keys not found in Redis"
    assert attempt_2_raw is not None, "Attempt 2 keys not found in Redis"
    assert (
        attempt_1_raw == attempt_2_raw
    ), "Keys shouldn't be different between attempts"

    last_sign = results.task_keys[-1]
    results.task_keys = results.task_keys[:-1]
    assert not results.is_key_in_keys(last_sign), "Last signature should not be in keys"
    assert results.model_dump(mode="json") == attempt_1_raw


@pytest.mark.asyncio(loop_scope="session")
async def test__retry_cache__durable_task_retry__no_duplicate_signatures(
    hatchet_client_init: HatchetInitData,
    test_ctx,
    ctx_metadata,
    trigger_options,
):
    # Arrange
    hatchet = hatchet_client_init.hatchet

    signature = await hatchet.asign(retry_cache_durable_task)
    msg = ContextMessage(base_data=test_ctx)

    # Act - trigger the durable task which will fail on attempt 1 and succeed on attempt 2
    wf_res = await signature.aio_run(msg, options=trigger_options)

    results = SignatureKeyWithWF(
        **wf_res["retry_cache_durable_task"]["hatchet_results"]
    )

    await _assert_retry_cache_idempotency(results)


@pytest.mark.asyncio(loop_scope="session")
async def test__retry_cache__task_retry__no_duplicate_signatures(
    test_ctx, ctx_metadata, trigger_options
):
    # Arrange
    msg = ContextMessage(base_data=test_ctx)

    # Act - trigger directly via hatchet aio_run (not through a signature)
    results = await retry_cache_durable_task.aio_run(msg, options=trigger_options)

    await _assert_retry_cache_idempotency(results)
