import asyncio

import pytest
from hatchet_sdk.clients.rest import V1TaskStatus
from thirdmagic.task import TaskSignature

from tests.integration.hatchet.assertions import get_runs
from tests.integration.hatchet.conftest import HatchetInitData
from tests.integration.hatchet.models import WorkflowTestMessage
from tests.integration.hatchet.worker import (
    test_dag_wf,
    test_dag_wf_hooks,
)

pytestmark = pytest.mark.hatchet


@pytest.mark.asyncio(loop_scope="session")
async def test_vanilla_dag_workflow_success(
    hatchet_client_init: HatchetInitData,
    test_ctx,
    ctx_metadata,
    trigger_options,
):
    hatchet = hatchet_client_init.hatchet
    message = WorkflowTestMessage(base_data=test_ctx)

    await test_dag_wf.aio_run_no_wait(message, options=trigger_options)

    await asyncio.sleep(15)
    runs = await get_runs(hatchet, ctx_metadata)

    assert len(runs) >= 1
    completed = [r for r in runs if r.status == V1TaskStatus.COMPLETED]
    assert len(completed) >= 1


@pytest.mark.asyncio(loop_scope="session")
async def test_vanilla_dag_workflow_failure(
    hatchet_client_init: HatchetInitData,
    test_ctx,
    ctx_metadata,
    trigger_options,
):
    hatchet = hatchet_client_init.hatchet
    message = WorkflowTestMessage(base_data=test_ctx, fail_at_step=2)

    await test_dag_wf.aio_run_no_wait(message, options=trigger_options)

    await asyncio.sleep(15)
    runs = await get_runs(hatchet, ctx_metadata)

    assert len(runs) >= 1
    failed = [r for r in runs if r.status == V1TaskStatus.FAILED]
    assert len(failed) >= 1


@pytest.mark.asyncio(loop_scope="session")
async def test_vanilla_dag_workflow_with_hooks_success(
    hatchet_client_init: HatchetInitData,
    test_ctx,
    ctx_metadata,
    trigger_options,
):
    hatchet = hatchet_client_init.hatchet
    message = WorkflowTestMessage(base_data=test_ctx)

    ref = await test_dag_wf_hooks.aio_run_no_wait(message, options=trigger_options)

    await asyncio.sleep(15)
    runs = await get_runs(hatchet, ctx_metadata)

    completed = [r for r in runs if r.status == V1TaskStatus.COMPLETED]
    assert len(completed) >= 1

    hook_key = f"user-hook-success:{ref.workflow_run_id}"
    hook_value = await TaskSignature.Meta.redis.get(hook_key)
    assert hook_value == "fired", f"User success hook did not fire (key={hook_key})"


@pytest.mark.asyncio(loop_scope="session")
async def test_vanilla_dag_workflow_with_hooks_failure(
    hatchet_client_init: HatchetInitData,
    test_ctx,
    ctx_metadata,
    trigger_options,
):
    hatchet = hatchet_client_init.hatchet
    message = WorkflowTestMessage(base_data=test_ctx, fail_at_step=2)

    ref = await test_dag_wf_hooks.aio_run_no_wait(message, options=trigger_options)

    await asyncio.sleep(15)
    runs = await get_runs(hatchet, ctx_metadata)

    failed = [r for r in runs if r.status == V1TaskStatus.FAILED]
    assert len(failed) >= 1

    hook_key = f"user-hook-failure:{ref.workflow_run_id}"
    hook_value = await TaskSignature.Meta.redis.get(hook_key)
    assert hook_value == "fired", f"User failure hook did not fire (key={hook_key})"
