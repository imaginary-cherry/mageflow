import pytest
from hatchet_sdk.clients.rest import V1TaskStatus

from tests.integration.hatchet.assertions import (
    assert_hook_fired,
    assert_workflow_run,
    get_runs,
)
from tests.integration.hatchet.conftest import HatchetInitData
from tests.integration.hatchet.models import (
    DagStep3Result,
    DagStepResult,
    ExpectedStepStatus,
    ExpectedWorkflowRun,
    WorkflowTestMessage,
)
from tests.integration.hatchet.worker import (
    dag_hooks_step1,
    dag_hooks_step2,
    dag_step1,
    dag_step2,
    dag_step3,
    test_dag_wf,
    test_dag_wf_hooks,
)

pytestmark = pytest.mark.hatchet

# --- Expected step results ---

_step1 = DagStepResult(step="1")
_step2 = DagStepResult(step="2")

DAG_WF_EXPECTED_OUTPUT = {
    dag_step1.name: _step1.model_dump(),
    dag_step2.name: _step2.model_dump(),
    dag_step3.name: DagStep3Result(
        step="3", parent_results=[_step1, _step2]
    ).model_dump(),
    # Hatchet SDK 1.23+ surfaces registered-but-not-fired lifecycle tasks
    # (on_failure) in the workflow result on successful runs. MageWorkflow
    # injects a noop on_failure hook, so it shows up here as skipped.
    "_noop_failure-on-failure": {"skipped": True},
}

DAG_WF_HOOKS_EXPECTED_OUTPUT = {
    dag_hooks_step1.name: DagStepResult(step="1").model_dump(),
    dag_hooks_step2.name: DagStepResult(step="2").model_dump(),
    # User-defined on_failure hook also appears as skipped on successful runs.
    "dag_hooks_on_failure-on-failure": {"skipped": True},
}

# --- Expected workflow runs per scenario ---

DAG_WF_SUCCESS = ExpectedWorkflowRun(
    workflow_status=V1TaskStatus.COMPLETED,
    expected_output=DAG_WF_EXPECTED_OUTPUT,
    steps=[
        ExpectedStepStatus(name=dag_step1.name, status=V1TaskStatus.COMPLETED),
        ExpectedStepStatus(name=dag_step2.name, status=V1TaskStatus.COMPLETED),
        ExpectedStepStatus(name=dag_step3.name, status=V1TaskStatus.COMPLETED),
    ],
)

DAG_WF_FAILURE = ExpectedWorkflowRun(
    workflow_status=V1TaskStatus.FAILED,
    steps=[
        ExpectedStepStatus(name=dag_step1.name, status=V1TaskStatus.COMPLETED),
        ExpectedStepStatus(name=dag_step2.name, status=V1TaskStatus.FAILED),
        ExpectedStepStatus(name=dag_step3.name, status=V1TaskStatus.CANCELLED),
    ],
)

DAG_WF_HOOKS_SUCCESS = ExpectedWorkflowRun(
    workflow_status=V1TaskStatus.COMPLETED,
    expected_output=DAG_WF_HOOKS_EXPECTED_OUTPUT,
    steps=[
        ExpectedStepStatus(name=dag_hooks_step1.name, status=V1TaskStatus.COMPLETED),
        ExpectedStepStatus(name=dag_hooks_step2.name, status=V1TaskStatus.COMPLETED),
        ExpectedStepStatus(
            name="dag_hooks_on_success-on-success", status=V1TaskStatus.COMPLETED
        ),
    ],
)

DAG_WF_HOOKS_FAILURE = ExpectedWorkflowRun(
    workflow_status=V1TaskStatus.FAILED,
    steps=[
        ExpectedStepStatus(name=dag_hooks_step1.name, status=V1TaskStatus.COMPLETED),
        ExpectedStepStatus(name=dag_hooks_step2.name, status=V1TaskStatus.FAILED),
        ExpectedStepStatus(
            name="dag_hooks_on_failure-on-failure", status=V1TaskStatus.COMPLETED
        ),
    ],
)


# --- Parametrize ---

WORKFLOW_SUCCESS_PARAMS = pytest.mark.parametrize(
    "workflow, expected_run",
    [
        pytest.param(test_dag_wf, DAG_WF_SUCCESS, id="no_hooks"),
        pytest.param(test_dag_wf_hooks, DAG_WF_HOOKS_SUCCESS, id="with_hooks"),
    ],
)

WORKFLOW_FAILURE_PARAMS = pytest.mark.parametrize(
    "workflow, expected_run",
    [
        pytest.param(test_dag_wf, DAG_WF_FAILURE, id="no_hooks"),
        pytest.param(test_dag_wf_hooks, DAG_WF_HOOKS_FAILURE, id="with_hooks"),
    ],
)


# --- Tests ---


@WORKFLOW_SUCCESS_PARAMS
@pytest.mark.asyncio(loop_scope="session")
async def test_vanilla_dag_workflow_success(
    hatchet_client_init: HatchetInitData,
    test_ctx,
    ctx_metadata,
    trigger_options,
    workflow,
    expected_run: ExpectedWorkflowRun,
):
    # Arrange
    hatchet = hatchet_client_init.hatchet
    message = WorkflowTestMessage(base_data=test_ctx)

    # Act
    result = await workflow.aio_run(message, options=trigger_options)

    # Assert
    assert result == expected_run.expected_output
    runs = await get_runs(hatchet, ctx_metadata)
    assert_workflow_run(runs, expected_run)


@WORKFLOW_FAILURE_PARAMS
@pytest.mark.asyncio(loop_scope="session")
async def test_vanilla_dag_workflow_failure(
    hatchet_client_init: HatchetInitData,
    test_ctx,
    ctx_metadata,
    trigger_options,
    workflow,
    expected_run: ExpectedWorkflowRun,
):
    # Arrange
    hatchet = hatchet_client_init.hatchet
    message = WorkflowTestMessage(base_data=test_ctx, fail_at_step=2)

    # Act & Assert
    with pytest.raises(Exception):
        await workflow.aio_run(message, options=trigger_options)

    runs = await get_runs(hatchet, ctx_metadata)
    assert_workflow_run(runs, expected_run)


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
    result = await ref.aio_result()

    # Assert
    assert result == DAG_WF_HOOKS_EXPECTED_OUTPUT
    runs = await get_runs(hatchet, ctx_metadata)
    assert_workflow_run(runs, DAG_WF_HOOKS_SUCCESS)
    await assert_hook_fired(redis_client, ref.workflow_run_id, "success")


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
    with pytest.raises(Exception):
        await ref.aio_result()

    # Assert
    runs = await get_runs(hatchet, ctx_metadata)
    assert_workflow_run(runs, DAG_WF_HOOKS_FAILURE)
    await assert_hook_fired(redis_client, ref.workflow_run_id, "failure")


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
    with pytest.raises(Exception):
        await ref.aio_result()

    # Assert
    runs = await get_runs(hatchet, ctx_metadata)
    assert_workflow_run(runs, DAG_WF_HOOKS_FAILURE)
    await assert_hook_fired(redis_client, ref.workflow_run_id, "failure")


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
    result = await ref.aio_result()

    # Assert
    assert result == DAG_WF_HOOKS_EXPECTED_OUTPUT
    runs = await get_runs(hatchet, ctx_metadata)
    assert_workflow_run(runs, DAG_WF_HOOKS_SUCCESS)
    await assert_hook_fired(redis_client, ref.workflow_run_id, "success")


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
    with pytest.raises(Exception):
        await ref.aio_result()

    # Assert
    runs = await get_runs(hatchet, ctx_metadata)
    assert_workflow_run(runs, DAG_WF_HOOKS_FAILURE)
    await assert_hook_fired(redis_client, ref.workflow_run_id, "failure")
