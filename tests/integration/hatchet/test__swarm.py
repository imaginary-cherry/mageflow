import asyncio
import uuid

import pytest
from hatchet_sdk.clients.rest import V1TaskStatus
from hatchet_sdk.runnables.workflow import TriggerWorkflowOptions

import orchestrator
from orchestrator import TaskSignature, CommandTaskMessage
from orchestrator.hatchet.swarm import SwarmConfig
from orchestrator.hatchet.config import orchestrator_config
from tests.integration.hatchet.conftest import (
    extract_bad_keys_from_redis,
    HatchetInitData,
)
from tests.integration.hatchet.worker import (
    task1,
    task2,
    task3,
    callback_with_redis,
    fail_task,
    error_callback,
)


@pytest.mark.asyncio(loop_scope="session")
async def test_swarm_with_three_tasks_integration_sanity(
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
    test_context = {"test_data": "swarm_test"}

    # Create task signatures for the swarm
    task1_sig = await TaskSignature.from_task(task1)
    task2_sig = await TaskSignature.from_task(task2)
    task3_sig = await TaskSignature.from_task(task3)

    # Create swarm callback signature using existing callback_with_redis task
    swarm_callback_sig = await TaskSignature.from_task(callback_with_redis)
    swarm = await orchestrator.swarm(
        tasks=[task1_sig, task2_sig, task3_sig],
        success_callbacks=[swarm_callback_sig],
        kwargs={"param1": "nice", "param2": ["test", 2]},
    )
    await swarm.close_swarm()
    swarm_tasks = [await TaskSignature.from_id(task) for task in swarm.tasks]
    task_name_to_be_called = {task.task_name: task for task in swarm_tasks}

    # Act
    # Test individual tasks directly to verify they work with the message format
    options = TriggerWorkflowOptions(additional_metadata={"test_run_id": test_run_id})
    regular_message = CommandTaskMessage(context=test_context)
    await swarm.aio_run_no_wait(regular_message, options=options)

    # Wait for all tasks to complete
    await asyncio.sleep(10)

    # Assert
    # Check that all subtasks were called by checking Hatchet runs
    runs = await hatchet.runs.aio_list(additional_metadata={"test_run_id": test_run_id})
    workflows_by_name = {wf.workflow_name: wf for wf in runs.rows}

    # Check that all subtask workflows were executed
    subtask_workflows = [
        wf for name, wf in workflows_by_name.items() if name in task_name_to_be_called
    ]
    assert len(subtask_workflows) == len(task_name_to_be_called)

    for wf in subtask_workflows:
        # Check that all subtasks completed successfully
        assert (
            wf.status == V1TaskStatus.COMPLETED
        ), f"Task {wf.workflow_name} - {wf.status}"

        # Check that the context was passed to the subtasks
        task_for_wf = task_name_to_be_called[wf.workflow_name]
        message = regular_message.model_copy()
        message.metadata.task_id = task_for_wf.id
        assert wf.input["input"]["context"] == test_context

    # Check that callback was called
    expected_output = [
        subtask.output["hatchet_results"] for subtask in subtask_workflows
    ]
    callback = workflows_by_name[callback_with_redis.name]
    assert callback.status == V1TaskStatus.COMPLETED
    for result in callback.input["input"]["task_result"]:
        assert any(
            [result == expected for expected in expected_output]
        ), f"{result} not found in {expected_output}"
    assert callback.input["input"]["context"] == test_context
    callback_calls = [
        wf
        for wf in workflows_by_name.values()
        if wf.workflow_name == callback_with_redis.name
    ]
    assert (
        len(callback_calls) == 1
    ), f"Callback workflow was not executed once {len(callback_calls)} times"

    # Check that Redis is clean except for persistent keys
    bad_keys = await extract_bad_keys_from_redis(redis_client)
    # One key - since the callback_with_redis task sets a key in Redis
    assert len(bad_keys) == 1, f"Redis should be clean but found keys: {bad_keys}"


@pytest.mark.asyncio(loop_scope="session")
async def test_swarm_with_mixed_success_failed_tasks_integration_edge_case(
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
    test_context = {"test_data": "swarm_mixed_tasks_test"}

    # Create task signatures: 3 success tasks only
    task1_sig = await TaskSignature.from_task(task1)
    task2_sig = await TaskSignature.from_task(task2)
    task3_sig = await TaskSignature.from_task(task3)
    fail_task_sig1 = await TaskSignature.from_task(fail_task)
    fail_task_sig2 = await TaskSignature.from_task(fail_task)
    fail_task_sig3 = await TaskSignature.from_task(fail_task)

    # Create swarm callback signature using an existing callback_with_redis task
    swarm_callback_sig = await TaskSignature.from_task(callback_with_redis)
    swarm_error_callback_sig = await TaskSignature.from_task(error_callback)
    swarm = await orchestrator.swarm(
        tasks=[
            task1_sig,
            task2_sig,
            task3_sig,
            fail_task_sig1,
            fail_task_sig2,
            fail_task_sig3,
        ],
        success_callbacks=[swarm_callback_sig],
        error_callbacks=[swarm_error_callback_sig],
        config=SwarmConfig(max_concurrency=2, stop_after_n_failures=2),
    )
    await swarm.close_swarm()

    # Act
    options = TriggerWorkflowOptions(additional_metadata={"test_run_id": test_run_id})
    regular_message = CommandTaskMessage(context=test_context)
    await swarm.aio_run_no_wait(regular_message, options=options)

    # Wait for tasks to complete
    await asyncio.sleep(10)

    # Assert
    # Get all workflow runs for this test
    runs = await hatchet.runs.aio_list(additional_metadata={"test_run_id": test_run_id})
    wf_names = set([wf.workflow_name for wf in runs.rows])
    workflows_by_name = {
        wf_name: [wf for wf in runs.rows if wf.workflow_name == wf_name]
        for wf_name in wf_names
    }

    # Check that success callback was called
    assert (
        callback_with_redis.name not in workflows_by_name
    ), f"Success callback no have been called"

    # Check error callback was activated
    error_callback_runs = workflows_by_name[error_callback.name]
    assert (
        len(error_callback_runs) == 1
    ), f"Error callback no have been called exactly once"
    error_callback_run = error_callback_runs[0]
    assert (
        error_callback_run.status == V1TaskStatus.COMPLETED
    ), f"Error callback should have failed"
    assert (
        error_callback_run.input["input"]["context"] == test_context
    ), f"Error context should be passed"

    # Check no task was activated after the last error
    error_wf = [
        wf for wf in workflows_by_name.values() if wf.workflow_name == fail_task.name
    ]
    last_error_wf = sorted(error_wf, key=lambda wf: wf.started_at)[-1]
    assert any(
        wf.started_at > last_error_wf.started_at for wf in workflows_by_name.values()
    )

    # Check that Redis is clean (success callback sets one key)
    bad_keys = await extract_bad_keys_from_redis(redis_client)
    assert len(bad_keys) == 0, f"Redis should be empty"
