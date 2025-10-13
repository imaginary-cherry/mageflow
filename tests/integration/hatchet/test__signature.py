import asyncio
import uuid

import pytest
from hatchet_sdk.clients.rest import V1TaskStatus
from hatchet_sdk.runnables.workflow import TriggerWorkflowOptions

import orchestrator
from orchestrator import TaskSignature, CommandTaskMessage
from orchestrator.hatchet.config import orchestrator_config

import orchestrator
from orchestrator import TaskSignature, CommandTaskMessage, CommandTaskMetadata
from orchestrator.hatchet.config import orchestrator_config
from orchestrator.hatchet.signature import SignatureStatus
from tests.integration.hatchet.conftest import (
    extract_bad_keys_from_redis,
    HatchetInitData,
)
from tests.integration.hatchet.worker import (
    task1,
    task1_callback,
    task2,
    error_callback,
    fail_task,
    sleep_task,
    callback_with_redis,
)


@pytest.mark.asyncio(loop_scope="session")
async def test_signature_creation_and_execution_with_redis_cleanup_sanity(
    hatchet_client_init: HatchetInitData,
):
    # Arrange
    redis_client, hatchet = (
        hatchet_client_init.redis_client,
        hatchet_client_init.hatchet,
    )
    test_run_id = uuid.uuid4().hex
    orchestrator_config.redis_client = redis_client
    orchestrator_config.hatchet_client = hatchet
    test_context = {"test_data": "signature_test"}
    message = CommandTaskMessage(context=test_context)

    # Act
    signature = await orchestrator.sign(task1)
    options = TriggerWorkflowOptions(additional_metadata={"test_run_id": test_run_id})
    ref = await signature.aio_run_no_wait(message, options=options)

    # Assert
    await asyncio.sleep(3)
    runs = await hatchet.runs.aio_list(additional_metadata={"test_run_id": test_run_id})
    workflows_by_name = {wf.workflow_name: wf for wf in runs.rows}

    assert task1.name in workflows_by_name
    task_workflow = workflows_by_name[task1.name]
    assert task_workflow.status == V1TaskStatus.COMPLETED
    assert task_workflow.input["input"]["context"] == test_context

    non_persistent_keys = await extract_bad_keys_from_redis(redis_client)
    assert (
        len(non_persistent_keys) == 0
    ), f"Not all redis keys were cleaned: {non_persistent_keys}"


@pytest.mark.asyncio(loop_scope="session")
async def test_signature_with_success_callbacks_execution_and_redis_cleanup_sanity(
    hatchet_client_init: HatchetInitData,
):
    # Arrange
    redis_client, hatchet = (
        hatchet_client_init.redis_client,
        hatchet_client_init.hatchet,
    )
    test_run_id = uuid.uuid4().hex
    orchestrator_config.redis_client = redis_client
    orchestrator_config.hatchet_client = hatchet
    test_context = {"test_data": "success_callback_test"}
    message = CommandTaskMessage(context=test_context)

    callback_signature = await TaskSignature.from_task(task1_callback)
    main_signature = await orchestrator.sign(task2, success_callbacks=[callback_signature])

    # Act
    options = TriggerWorkflowOptions(additional_metadata={"test_run_id": test_run_id})
    ref = await main_signature.aio_run_no_wait(message, options=options)

    # Assert
    await asyncio.sleep(3)
    runs = await hatchet.runs.aio_list(additional_metadata={"test_run_id": test_run_id})
    workflows_by_name = {wf.workflow_name: wf for wf in runs.rows}

    assert task2.name in workflows_by_name
    assert task1_callback.name in workflows_by_name

    main_workflow = workflows_by_name[task2.name]
    callback_workflow = workflows_by_name[task1_callback.name]

    assert main_workflow.status == V1TaskStatus.COMPLETED
    assert callback_workflow.status == V1TaskStatus.COMPLETED
    assert main_workflow.input["input"]["context"] == test_context
    assert callback_workflow.input["input"]["context"] == test_context

    non_persistent_keys = await extract_bad_keys_from_redis(redis_client)
    assert (
        len(non_persistent_keys) == 0
    ), f"Not all redis keys were cleaned: {non_persistent_keys}"


@pytest.mark.asyncio(loop_scope="session")
async def test_signature_with_error_callbacks_execution_and_redis_cleanup_sanity(
    hatchet_client_init: HatchetInitData,
):
    # Arrange
    redis_client, hatchet = (
        hatchet_client_init.redis_client,
        hatchet_client_init.hatchet,
    )
    test_run_id = uuid.uuid4().hex
    orchestrator_config.redis_client = redis_client
    orchestrator_config.hatchet_client = hatchet
    test_context = {"test_data": "error_callback_test"}
    message = CommandTaskMessage(context=test_context)

    error_callback_signature = await orchestrator.sign(error_callback)

    # Act
    options = TriggerWorkflowOptions(additional_metadata={"test_run_id": test_run_id})
    ref = await error_callback_signature.aio_run_no_wait(message, options=options)

    # Assert
    await asyncio.sleep(2)
    runs = await hatchet.runs.aio_list(additional_metadata={"test_run_id": test_run_id})
    workflows_by_name = {wf.workflow_name: wf for wf in runs.rows}

    assert error_callback.name in workflows_by_name
    error_workflow = workflows_by_name[error_callback.name]

    assert error_workflow.status == V1TaskStatus.COMPLETED
    assert error_workflow.input["input"]["context"] == test_context

    non_persistent_keys = await extract_bad_keys_from_redis(redis_client)
    assert (
        len(non_persistent_keys) == 0
    ), f"Not all redis keys were cleaned: {non_persistent_keys}"


@pytest.mark.asyncio(loop_scope="session")
async def test_signature_from_registered_task_name_execution_and_redis_cleanup_sanity(
    hatchet_client_init: HatchetInitData,
):
    # Arrange
    redis_client, hatchet = (
        hatchet_client_init.redis_client,
        hatchet_client_init.hatchet,
    )
    test_run_id = uuid.uuid4().hex
    orchestrator_config.redis_client = redis_client
    orchestrator_config.hatchet_client = hatchet
    test_context = {"test_data": "registered_task_name_test"}
    message = CommandTaskMessage(context=test_context)

    registered_task_name = "task1-test"

    # Act
    signature = await orchestrator.sign(
        registered_task_name, input_validator=orchestrator.CommandTaskMessage
    )
    options = TriggerWorkflowOptions(additional_metadata={"test_run_id": test_run_id})
    ref = await signature.aio_run_no_wait(message, options=options)

    # Assert
    await asyncio.sleep(3)
    runs = await hatchet.runs.aio_list(additional_metadata={"test_run_id": test_run_id})
    workflows_by_name = {wf.workflow_name: wf for wf in runs.rows}

    assert task1.name in workflows_by_name
    task_workflow = workflows_by_name[task1.name]
    assert task_workflow.status == V1TaskStatus.COMPLETED
    assert task_workflow.input["input"]["context"] == test_context

    non_persistent_keys = await extract_bad_keys_from_redis(redis_client)
    assert (
        len(non_persistent_keys) == 0
    ), f"Not all redis keys were cleaned: {non_persistent_keys}"


@pytest.mark.asyncio(loop_scope="session")
async def test_task_with_success_callback_execution_and_redis_cleanup_sanity(
    hatchet_client_init: HatchetInitData,
):
    # Arrange
    redis_client, hatchet = (
        hatchet_client_init.redis_client,
        hatchet_client_init.hatchet,
    )
    test_run_id = uuid.uuid4().hex
    orchestrator_config.redis_client = redis_client
    orchestrator_config.hatchet_client = hatchet
    test_context = {"test_data": "task_success_callback_test"}

    success_callback_signature = await orchestrator.sign(task1_callback)
    message = CommandTaskMessage(context=test_context)
    task = await orchestrator.sign(
        task2, success_callbacks=[success_callback_signature.id]
    )

    # Act
    options = TriggerWorkflowOptions(additional_metadata={"test_run_id": test_run_id})
    ref = await task.aio_run_no_wait(message, options=options)

    # Assert
    await asyncio.sleep(3)
    runs = await hatchet.runs.aio_list(additional_metadata={"test_run_id": test_run_id})
    workflows_by_name = {wf.workflow_name: wf for wf in runs.rows}

    assert task2.name in workflows_by_name
    assert task1_callback.name in workflows_by_name

    main_workflow = workflows_by_name[task2.name]
    callback_workflow = workflows_by_name[task1_callback.name]

    assert main_workflow.status == V1TaskStatus.COMPLETED
    assert callback_workflow.status == V1TaskStatus.COMPLETED
    assert main_workflow.input["input"]["context"] == test_context
    assert callback_workflow.input["input"]["context"] == test_context

    non_persistent_keys = await extract_bad_keys_from_redis(redis_client)
    assert (
        len(non_persistent_keys) == 0
    ), f"Not all redis keys were cleaned: {non_persistent_keys}"


@pytest.mark.asyncio(loop_scope="session")
async def test_task_with_failure_callback_execution_and_redis_cleanup_sanity(
    hatchet_client_init: HatchetInitData,
):
    # Arrange
    redis_client, hatchet = (
        hatchet_client_init.redis_client,
        hatchet_client_init.hatchet,
    )
    test_run_id = uuid.uuid4().hex
    orchestrator_config.redis_client = redis_client
    orchestrator_config.hatchet_client = hatchet
    test_context = {"test_data": "task_failure_callback_test"}

    error_callback_signature = await orchestrator.sign(error_callback)
    message = CommandTaskMessage(context=test_context)
    task = await orchestrator.sign(fail_task, error_callbacks=[error_callback_signature])

    # Act
    options = TriggerWorkflowOptions(additional_metadata={"test_run_id": test_run_id})
    ref = await task.aio_run_no_wait(message, options=options)

    # Assert
    await asyncio.sleep(3)
    runs = await hatchet.runs.aio_list(additional_metadata={"test_run_id": test_run_id})
    workflows_by_name = {wf.workflow_name: wf for wf in runs.rows}

    assert error_callback.name in workflows_by_name

    fail_workflow = workflows_by_name[fail_task.name]
    assert fail_workflow.input["input"]["context"] == test_context

    assert error_callback.name in workflows_by_name
    error_workflow = workflows_by_name[error_callback.name]
    assert error_workflow.status == V1TaskStatus.COMPLETED
    assert error_workflow.input["input"]["context"] == test_context

    await error_callback_signature.remove()

    non_persistent_keys = await extract_bad_keys_from_redis(redis_client)
    assert (
        len(non_persistent_keys) == 0
    ), f"Not all redis keys were cleaned: {non_persistent_keys}"


@pytest.mark.asyncio(loop_scope="session")
async def test_signature_stop_with_callback_redis_cleanup_sanity(
    hatchet_client_init: HatchetInitData,
):
    # Arrange
    redis_client, hatchet = (
        hatchet_client_init.redis_client,
        hatchet_client_init.hatchet,
    )
    test_run_id = uuid.uuid4().hex
    test_id = uuid.uuid4().hex
    orchestrator_config.redis_client = redis_client
    orchestrator_config.hatchet_client = hatchet
    test_context = {"test_data": "signature_stop_test", "test_id": test_id}
    message = CommandTaskMessage(context=test_context)

    callback_signature = await orchestrator.sign(callback_with_redis)
    main_signature = await orchestrator.sign(
        sleep_task, success_callbacks=[callback_signature]
    )

    # Act
    options = TriggerWorkflowOptions(additional_metadata={"test_run_id": test_run_id})
    await callback_signature.change_status(SignatureStatus.STOPPED)
    ref = await main_signature.aio_run_no_wait(message, options=options)

    # Assert
    await asyncio.sleep(5)
    runs = await hatchet.runs.aio_list(additional_metadata={"test_run_id": test_run_id})
    workflows_by_name = {wf.workflow_name: wf for wf in runs.rows}

    # Check the main task exists but was stopped
    assert sleep_task.name in workflows_by_name

    # Check callback was not activated
    redis_keys = await redis_client.keys("*")
    assert not any(
        key.decode().startswith(f"activated-task-") for key in redis_keys
    ), f"Callback was activated even though it was stopped"

    # Check kwargs were stored
    hatchet_call = workflows_by_name[callback_with_redis.name]
    updated_callback_signature = await TaskSignature.from_id(callback_signature.id)
    expected_dump = callback_with_redis.input_validator.validate(
        hatchet_call.input["input"]
    )
    assert updated_callback_signature.kwargs == expected_dump.model_dump()


@pytest.mark.asyncio(loop_scope="session")
async def test__set_result_in_return_value(hatchet_client_init: HatchetInitData):
    # Arrange
    redis_client, hatchet = (
        hatchet_client_init.redis_client,
        hatchet_client_init.hatchet,
    )
    test_run_id = uuid.uuid4().hex
    orchestrator_config.redis_client = redis_client
    orchestrator_config.hatchet_client = hatchet
    test_context = {}

    callback_signature = await TaskSignature.from_task(callback_with_redis)
    msg_callback_signature = await TaskSignature.from_task(callback_with_redis)
    main_signature = await TaskSignature.from_task(
        sleep_task, success_callbacks=[callback_signature]
    )
    message = CommandTaskMessage(
        context=test_context,
        metadata=CommandTaskMetadata(on_success=msg_callback_signature.id),
    )

    # Act
    options = TriggerWorkflowOptions(additional_metadata={"test_run_id": test_run_id})
    await callback_signature.change_status(SignatureStatus.STOPPED)
    await main_signature.aio_run_no_wait(message, options=options)

    # Assert
    await asyncio.sleep(5)
    runs = await hatchet.runs.aio_list(additional_metadata={"test_run_id": test_run_id})
    runs_with_callback = [
        wf for wf in runs.rows if wf.workflow_name == callback_with_redis.name
    ]
    assert len(runs_with_callback) == 2, "Callback workflow was not executed"
