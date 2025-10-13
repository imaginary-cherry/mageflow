import asyncio
import uuid

import orchestrator
import pytest
from orchestrator import TaskSignature, CommandTaskMessage
from orchestrator.hatchet.config import orchestrator_config
from hatchet_sdk.clients.rest import V1TaskStatus
from hatchet_sdk.runnables.workflow import TriggerWorkflowOptions

from tests.integration.hatchet.conftest import (
    extract_bad_keys_from_redis,
    HatchetInitData,
)
from tests.integration.hatchet.worker import (
    task1,
    task1_callback,
    task2,
    task3,
    chain_callback,
    fail_task,
    error_callback,
)


@pytest.mark.asyncio(loop_scope="session")
async def test_chain_integration(hatchet_client_init: HatchetInitData):
    # Arrange
    redis_client, hatchet = (
        hatchet_client_init.redis_client,
        hatchet_client_init.hatchet,
    )
    test_run_id = uuid.uuid4().hex
    orchestrator_config.redis_client = redis_client
    orchestrator_config.hatchet_client = hatchet
    chain_context = {"chain_data": 123123}
    message = CommandTaskMessage(context=chain_context)

    signature1 = await TaskSignature.from_task(task1)
    signature1_callback = await TaskSignature.from_task(task1_callback)
    signature2 = await TaskSignature.from_task(
        task2, success_callbacks=[signature1_callback]
    )
    chain_success_error_callback = await TaskSignature.from_task(error_callback)
    success_chain_signature = await TaskSignature.from_task(
        chain_callback, error_callbacks=[chain_success_error_callback]
    )

    expected_order = [task1.name, task2.name, task3.name]
    expected_callbacks = [task1_callback.name, chain_callback.name]

    # Act
    chain_signature = await orchestrator.chain(
        [signature1, signature2.id, task3],
        success=success_chain_signature,
    )

    options = TriggerWorkflowOptions(additional_metadata={"test_run_id": test_run_id})
    ref = await chain_signature.aio_run_no_wait(message, options=options)

    # Assert
    await asyncio.sleep(10)
    runs = await hatchet.runs.aio_list(additional_metadata={"test_run_id": test_run_id})
    workflows_by_name = {wf.workflow_name: wf for wf in runs.rows}

    # Check all chain tasks recieve the context
    for wf in workflows_by_name.values():
        wf_ctx = wf.input["input"]["context"]
        assert wf_ctx == chain_context, f"Context was not passed to {wf.workflow_name}"

    # Check the task in chain were called in order
    for i in range(len(expected_order) - 1):
        curr_wf = workflows_by_name[expected_order[i]]
        assert (
            curr_wf.status == V1TaskStatus.COMPLETED
        ), f"Task {curr_wf.workflow_name} - {curr_wf.status}"
        next_wf = workflows_by_name[expected_order[i + 1]]
        assert (
            curr_wf.started_at < next_wf.started_at
        ), f"Task {curr_wf.workflow_name} started after {next_wf.workflow_name}"

    last_wf = workflows_by_name[expected_order[-1]]
    assert last_wf.status == V1TaskStatus.COMPLETED

    # Check that callback were called
    for callback in expected_callbacks:
        assert workflows_by_name[callback].status == V1TaskStatus.COMPLETED

    # Check redis is clean
    non_persistent_keys = await extract_bad_keys_from_redis(redis_client)
    assert (
        len(non_persistent_keys) == 0
    ), f"Not all redis keys were cleaned: {non_persistent_keys}"


@pytest.mark.asyncio(loop_scope="session")
async def test_chain_fail(hatchet_client_init: HatchetInitData):
    # Arrange
    redis_client, hatchet = (
        hatchet_client_init.redis_client,
        hatchet_client_init.hatchet,
    )
    test_run_id = uuid.uuid4().hex
    orchestrator_config.redis_client = redis_client
    orchestrator_config.hatchet_client = hatchet
    chain_context = {"chain_data": 123123}
    message = CommandTaskMessage(context=chain_context)

    signature1 = await TaskSignature.from_task(task1)
    chain_success_error_callback = await TaskSignature.from_task(error_callback)
    success_chain_signature = await TaskSignature.from_task(chain_callback)

    expected_callbacks = [error_callback.name]

    # Act
    chain_signature = await orchestrator.chain(
        [signature1, fail_task, task3],
        success=success_chain_signature,
        error=chain_success_error_callback,
    )

    options = TriggerWorkflowOptions(additional_metadata={"test_run_id": test_run_id})
    ref = await chain_signature.aio_run_no_wait(message, options=options)

    # Assert
    await asyncio.sleep(5)
    runs = await hatchet.runs.aio_list(additional_metadata={"test_run_id": test_run_id})
    workflows_by_name = {wf.workflow_name: wf for wf in runs.rows}

    # Check task were not called
    assert task3.name not in workflows_by_name

    # Check that callback were called
    for callback in expected_callbacks:
        assert workflows_by_name[callback].status == V1TaskStatus.COMPLETED
        assert workflows_by_name[callback].input["input"]["context"] == chain_context

    # Check redis is clean
    non_persistent_keys = await extract_bad_keys_from_redis(redis_client)
    assert (
        len(non_persistent_keys) == 0
    ), f"Not all redis keys were cleaned: {non_persistent_keys}"
