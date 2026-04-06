import asyncio

import pytest
from hatchet_sdk.clients.rest import V1TaskStatus

from tests.integration.hatchet.assertions import get_runs
from tests.integration.hatchet.conftest import HatchetInitData
from tests.integration.hatchet.models import WorkflowTestMessage
from tests.integration.hatchet.worker import (
    test_dag_wf,
    test_dag_wf_hooks,
)

pytestmark = pytest.mark.hatchet

WORKFLOW_PARAMS = pytest.mark.parametrize(
    "workflow",
    [
        pytest.param(test_dag_wf, id="no_hooks"),
        pytest.param(test_dag_wf_hooks, id="with_hooks"),
    ],
)


@WORKFLOW_PARAMS
@pytest.mark.asyncio(loop_scope="session")
async def test_vanilla_dag_workflow_success(
    hatchet_client_init: HatchetInitData,
    test_ctx,
    ctx_metadata,
    trigger_options,
    workflow,
):
    # Arrange
    hatchet = hatchet_client_init.hatchet
    message = WorkflowTestMessage(base_data=test_ctx)

    # Act
    await workflow.aio_run_no_wait(message, options=trigger_options)

    # Assert
    await asyncio.sleep(7)
    runs = await get_runs(hatchet, ctx_metadata)
    assert len(runs) >= 1
    completed = [r for r in runs if r.status == V1TaskStatus.COMPLETED]
    assert len(completed) >= 1


@WORKFLOW_PARAMS
@pytest.mark.asyncio(loop_scope="session")
async def test_vanilla_dag_workflow_failure(
    hatchet_client_init: HatchetInitData,
    test_ctx,
    ctx_metadata,
    trigger_options,
    workflow,
):
    # Arrange
    hatchet = hatchet_client_init.hatchet
    message = WorkflowTestMessage(base_data=test_ctx, fail_at_step=2)

    # Act
    await workflow.aio_run_no_wait(message, options=trigger_options)

    # Assert
    await asyncio.sleep(7)
    runs = await get_runs(hatchet, ctx_metadata)
    assert len(runs) >= 1
    failed = [r for r in runs if r.status == V1TaskStatus.FAILED]
    assert len(failed) >= 1


@pytest.mark.asyncio(loop_scope="session")
async def test_vanilla_dag_workflow_hooks_success_fires(
    hatchet_client_init: HatchetInitData,
    test_ctx,
    ctx_metadata,
    trigger_options,
):
    # Arrange
    redis_client = hatchet_client_init.redis_client
    hatchet = hatchet_client_init.hatchet
    message = WorkflowTestMessage(base_data=test_ctx)

    # Act
    ref = await test_dag_wf_hooks.aio_run_no_wait(message, options=trigger_options)

    # Assert
    await asyncio.sleep(7)
    runs = await get_runs(hatchet, ctx_metadata)
    completed = [r for r in runs if r.status == V1TaskStatus.COMPLETED]
    assert len(completed) >= 1
    hook_key = f"user-hook-success:{ref.workflow_run_id}"
    hook_value = await redis_client.get(hook_key)
    assert hook_value == "fired", f"User success hook did not fire (key={hook_key})"


@pytest.mark.asyncio(loop_scope="session")
async def test_vanilla_dag_workflow_hooks_failure_fires(
    hatchet_client_init: HatchetInitData,
    test_ctx,
    ctx_metadata,
    trigger_options,
):
    # Arrange
    redis_client = hatchet_client_init.redis_client
    hatchet = hatchet_client_init.hatchet
    message = WorkflowTestMessage(base_data=test_ctx, fail_at_step=2)

    # Act
    ref = await test_dag_wf_hooks.aio_run_no_wait(message, options=trigger_options)

    # Assert
    await asyncio.sleep(7)
    runs = await get_runs(hatchet, ctx_metadata)
    failed = [r for r in runs if r.status == V1TaskStatus.FAILED]
    assert len(failed) >= 1
    hook_key = f"user-hook-failure:{ref.workflow_run_id}"
    hook_value = await redis_client.get(hook_key)
    assert hook_value == "fired", f"User failure hook did not fire (key={hook_key})"


@pytest.mark.asyncio(loop_scope="session")
async def test_vanilla_dag_workflow_timeout(
    hatchet_client_init: HatchetInitData,
    test_ctx,
    ctx_metadata,
    trigger_options,
):
    # Arrange
    redis_client = hatchet_client_init.redis_client
    hatchet = hatchet_client_init.hatchet
    message = WorkflowTestMessage(base_data=test_ctx, timeout_at_step=2)

    # Act
    ref = await test_dag_wf_hooks.aio_run_no_wait(message, options=trigger_options)

    # Assert
    await asyncio.sleep(15)
    runs = await get_runs(hatchet, ctx_metadata)
    assert len(runs) >= 1
    failed = [r for r in runs if r.status == V1TaskStatus.FAILED]
    assert len(failed) >= 1
    hook_key = f"user-hook-failure:{ref.workflow_run_id}"
    hook_value = await redis_client.get(hook_key)
    assert hook_value == "fired", f"User failure hook did not fire (key={hook_key})"


@pytest.mark.asyncio(loop_scope="session")
async def test_vanilla_dag_workflow_retry_then_succeed(
    hatchet_client_init: HatchetInitData,
    test_ctx,
    ctx_metadata,
    trigger_options,
):
    # Arrange
    redis_client = hatchet_client_init.redis_client
    hatchet = hatchet_client_init.hatchet
    message = WorkflowTestMessage(
        base_data=test_ctx, retry_at_step=1, retry_succeed_on_attempt=2
    )

    # Act
    ref = await test_dag_wf_hooks.aio_run_no_wait(message, options=trigger_options)

    # Assert
    await asyncio.sleep(15)
    runs = await get_runs(hatchet, ctx_metadata)
    assert len(runs) >= 1
    completed = [r for r in runs if r.status == V1TaskStatus.COMPLETED]
    assert len(completed) >= 1
    hook_key = f"user-hook-success:{ref.workflow_run_id}"
    hook_value = await redis_client.get(hook_key)
    assert hook_value == "fired", f"User success hook did not fire (key={hook_key})"


@pytest.mark.asyncio(loop_scope="session")
async def test_vanilla_dag_workflow_retry_to_failure(
    hatchet_client_init: HatchetInitData,
    test_ctx,
    ctx_metadata,
    trigger_options,
):
    # Arrange
    redis_client = hatchet_client_init.redis_client
    hatchet = hatchet_client_init.hatchet
    message = WorkflowTestMessage(base_data=test_ctx, retry_at_step=2)

    # Act
    ref = await test_dag_wf_hooks.aio_run_no_wait(message, options=trigger_options)

    # Assert
    await asyncio.sleep(20)
    runs = await get_runs(hatchet, ctx_metadata)
    assert len(runs) >= 1
    failed = [r for r in runs if r.status == V1TaskStatus.FAILED]
    assert len(failed) >= 1
    hook_key = f"user-hook-failure:{ref.workflow_run_id}"
    hook_value = await redis_client.get(hook_key)
    assert hook_value == "fired", f"User failure hook did not fire (key={hook_key})"
