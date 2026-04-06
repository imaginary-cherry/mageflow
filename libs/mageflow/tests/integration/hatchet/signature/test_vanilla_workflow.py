import asyncio

import pytest
from hatchet_sdk.clients.rest import V1TaskStatus
from thirdmagic.task import TaskSignature

from tests.integration.hatchet.assertions import get_runs
from tests.integration.hatchet.conftest import HatchetInitData
from tests.integration.hatchet.models import ContextMessage
from tests.integration.hatchet.worker import (
    chain_test_wf,
    chain_test_wf_fail,
    chain_test_wf_hooks,
    chain_test_wf_hooks_fail,
)


@pytest.mark.asyncio(loop_scope="session")
async def test_vanilla_workflow_no_hooks_success(
    hatchet_client_init: HatchetInitData,
    test_ctx,
    ctx_metadata,
    trigger_options,
):
    # Arrange
    hatchet = hatchet_client_init.hatchet
    message = ContextMessage(base_data=test_ctx)

    # Act
    await chain_test_wf.aio_run_no_wait(message, options=trigger_options)

    # Assert
    await asyncio.sleep(15)
    runs = await get_runs(hatchet, ctx_metadata)

    assert len(runs) >= 1
    # Find the main workflow run (not internal mageflow tasks)
    completed = [r for r in runs if r.status == V1TaskStatus.COMPLETED]
    assert len(completed) >= 1


@pytest.mark.asyncio(loop_scope="session")
async def test_vanilla_workflow_no_hooks_failure(
    hatchet_client_init: HatchetInitData,
    test_ctx,
    ctx_metadata,
    trigger_options,
):
    # Arrange
    hatchet = hatchet_client_init.hatchet
    message = ContextMessage(base_data=test_ctx)

    # Act
    await chain_test_wf_fail.aio_run_no_wait(message, options=trigger_options)

    # Assert
    await asyncio.sleep(15)
    runs = await get_runs(hatchet, ctx_metadata)

    assert len(runs) >= 1
    failed = [r for r in runs if r.status == V1TaskStatus.FAILED]
    assert len(failed) >= 1


@pytest.mark.asyncio(loop_scope="session")
async def test_vanilla_workflow_with_hooks_success(
    hatchet_client_init: HatchetInitData,
    test_ctx,
    ctx_metadata,
    trigger_options,
):
    # Arrange
    redis_client = hatchet_client_init.redis_client
    hatchet = hatchet_client_init.hatchet
    message = ContextMessage(base_data=test_ctx)

    # Act
    ref = await chain_test_wf_hooks.aio_run_no_wait(message, options=trigger_options)

    # Assert
    await asyncio.sleep(15)
    runs = await get_runs(hatchet, ctx_metadata)

    completed = [r for r in runs if r.status == V1TaskStatus.COMPLETED]
    assert len(completed) >= 1

    # Verify user-defined success hook fired
    hook_key = f"user-hook-success:{ref.workflow_run_id}"
    hook_value = await TaskSignature.Meta.redis.get(hook_key)
    assert hook_value == "fired", (
        f"User success hook did not fire (key={hook_key})"
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_vanilla_workflow_with_hooks_failure(
    hatchet_client_init: HatchetInitData,
    test_ctx,
    ctx_metadata,
    trigger_options,
):
    # Arrange
    redis_client = hatchet_client_init.redis_client
    hatchet = hatchet_client_init.hatchet
    message = ContextMessage(base_data=test_ctx)

    # Act
    ref = await chain_test_wf_hooks_fail.aio_run_no_wait(
        message, options=trigger_options
    )

    # Assert
    await asyncio.sleep(15)
    runs = await get_runs(hatchet, ctx_metadata)

    failed = [r for r in runs if r.status == V1TaskStatus.FAILED]
    assert len(failed) >= 1

    # Verify user-defined failure hook fired
    hook_key = f"user-hook-failure:{ref.workflow_run_id}"
    hook_value = await TaskSignature.Meta.redis.get(hook_key)
    assert hook_value == "fired", (
        f"User failure hook did not fire (key={hook_key})"
    )
