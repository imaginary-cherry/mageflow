import asyncio
from datetime import datetime

from hatchet_sdk import Hatchet
from hatchet_sdk.clients.rest import V1LogLineList, V1TaskStatus, V1TaskSummary
from hatchet_sdk.runnables.workflow import TaskRunRef
from pydantic import BaseModel
from thirdmagic.chain.model import ChainTaskSignature
from thirdmagic.consts import (
    MAGEFLOW_TASK_INITIALS,
    TASK_ID_PARAM_NAME,
)
from thirdmagic.signature import Signature
from thirdmagic.swarm.model import SwarmTaskSignature
from thirdmagic.task import TaskSignature
from thirdmagic.utils import return_value_field

from tests.integration.hatchet.conftest import extract_bad_keys_from_redis
from tests.integration.hatchet.models import ExpectedWorkflowRun
from tests.integration.hatchet.worker import MAX_DONE_TTL

WF_MAPPING_TYPE = dict[str, V1TaskSummary]
WF_MAPPING_BY_WF_ID_TYPE = dict[str, V1TaskSummary]
HatchetRuns = list[V1TaskSummary]


def _task_error_info(wf: V1TaskSummary) -> str:
    parts = [f"status={wf.status}"]
    if wf.error_message:
        parts.append(f"error={wf.error_message}")
    return " | ".join(parts)


def is_wf_internal_mageflow(hatchet: Hatchet, wf: V1TaskSummary) -> bool:
    if wf.workflow_name is None:
        return False
    task_name = wf.workflow_name.removeprefix(hatchet.namespace)
    return task_name.startswith(MAGEFLOW_TASK_INITIALS)


async def get_specific_refs(
    hatchet: Hatchet, refs: list[TaskRunRef]
) -> list[V1TaskSummary]:
    wf_tasks = await asyncio.gather(
        *[hatchet.runs.aio_get_task_run(ref.workflow_run_id) for ref in refs]
    )
    return wf_tasks


def is_workflow(run: V1TaskSummary) -> bool:
    # Also can check run.task_id == 0
    return run.children is not None


async def get_full_run(hatchet: Hatchet, wf: V1TaskSummary) -> V1TaskSummary:
    if is_workflow(wf):
        return wf
    full_wf = await hatchet.runs.aio_get_task_run(wf.task_external_id)
    full_wf.workflow_name = wf.workflow_name
    return full_wf


async def get_runs(hatchet: Hatchet, ctx_metadata: dict) -> HatchetRuns:
    runs = await hatchet.runs.aio_list(additional_metadata=ctx_metadata)
    # Retrieve tasks data
    wf_tasks = await asyncio.gather(*[get_full_run(hatchet, wf) for wf in runs.rows])
    return wf_tasks


def map_wf_by_external_id(runs: HatchetRuns) -> WF_MAPPING_BY_WF_ID_TYPE:
    return {wf.workflow_run_external_id: wf for wf in runs}


def map_wf_by_id(
    runs: HatchetRuns, also_not_done: bool = False, ignore_cancel: bool = False
) -> WF_MAPPING_TYPE:
    return {
        task_id: wf
        for wf in runs
        if (task_id := get_task_param(wf, TASK_ID_PARAM_NAME))
        if also_not_done or is_wf_done(wf)
        if not ignore_cancel or not is_task_paused(wf)
    }


def find_sub_calls_from_wf(
    hatchet: Hatchet, origin_wf: V1TaskSummary, runs: HatchetRuns
) -> list[V1TaskSummary]:
    called_tasks = [
        wf for wf in runs if wf.parent_task_external_id == origin_wf.task_external_id
    ]
    for wf in called_tasks[:]:
        if is_wf_internal_mageflow(hatchet, wf):
            called_tasks.remove(wf)
            called_tasks.extend(find_sub_calls_from_wf(hatchet, wf, runs))

    return called_tasks


def find_called_task_from_run_in_swarm(
    hatchet: Hatchet, task_ref: TaskRunRef, runs: HatchetRuns
) -> V1TaskSummary:
    wf_by_id = map_wf_by_external_id(runs)
    ref_wf = wf_by_id[task_ref.workflow_run_id]

    called_task = find_sub_calls_from_wf(hatchet, ref_wf, runs)
    assert called_task, "No task was called from run in swarm"
    return called_task[0]


def find_sub_calls_by_task_ref(
    hatchet: Hatchet, wf: V1TaskSummary, runs: HatchetRuns
) -> list[V1TaskSummary]:
    called_tasks = find_sub_calls_from_wf(hatchet, wf, runs)
    return called_tasks


def is_wf_done(wf: V1TaskSummary) -> bool:
    wf_output = wf.output or {}
    completed = wf.status == V1TaskStatus.COMPLETED
    # hatchet workflow doesn't wrap with hatchet results
    correct_results_pattern = is_workflow(wf) or "hatchet_results" in wf_output
    task_succeeded = completed and correct_results_pattern
    return task_succeeded or wf.status == V1TaskStatus.FAILED


def is_task_paused(wf: V1TaskSummary) -> bool:
    return wf.status == V1TaskStatus.CANCELLED


def get_task_param(wf: V1TaskSummary, param_name: str):
    if wf.additional_metadata is None:
        return None
    return wf.additional_metadata.get(param_name)


def assert_signature_done(
    runs: HatchetRuns,
    task_sign: TaskSignature,
    hatchet_task_results=None,
    check_called_once=True,
    check_finished_once=True,
    allow_fails=False,
    **input_params,
) -> V1TaskSummary:
    task_sign_key = task_sign.key
    task_name = task_sign.task_name

    if check_called_once or check_finished_once:
        task_id_calls = [
            wf
            for wf in runs
            if get_task_param(wf, TASK_ID_PARAM_NAME) == task_sign_key
            # If we just want to check that the task was finished once,
            # In this case it is ok if the task was called more than once (For suspended tasks cases)
            if check_called_once or is_wf_done(wf)
        ]
        assert (
            len(task_id_calls) == 1
        ), f"Task {task_name} - {task_sign_key} was called more than once or not at all: {task_id_calls}"

    wf_by_task_id = map_wf_by_id(runs, also_not_done=True, ignore_cancel=True)
    return _assert_task_done(
        task_sign, wf_by_task_id, input_params, hatchet_task_results, allow_fails
    )


def assert_signature_failed(
    runs: HatchetRuns, task_sign: TaskSignature
) -> V1TaskSummary:
    wf_by_task_id = map_wf_by_id(runs, also_not_done=True)
    assert task_sign.key in wf_by_task_id, f"{task_sign.key} was not called"
    summary = wf_by_task_id[task_sign.key]
    assert (
        summary.status == V1TaskStatus.FAILED
        or summary.status == V1TaskStatus.CANCELLED
    ), f"{task_sign.key} was not failed ({_task_error_info(summary)})"
    return summary


def _assert_task_done(
    task: Signature,
    wf_map: WF_MAPPING_TYPE,
    input_params: dict = None,
    results=None,
    allow_fails=False,
) -> V1TaskSummary:
    task_id = task.key
    assert task_id in wf_map
    task_workflow = wf_map[task_id]
    if not allow_fails:
        assert (
            task_workflow.status == V1TaskStatus.COMPLETED
        ), f"{task_workflow.workflow_name} didn't finish ({_task_error_info(task_workflow)})"
    if input_params is not None:
        task_input = task_workflow.input.get("input", {})
        assert (
            input_params.keys() <= task_input.keys()
        ), f"missing params {input_params.keys() - task_input.keys()} for {task_workflow.workflow_name}"
        assert (
            input_params.items() <= task_input.items()
        ), f"{task_workflow.workflow_name} has some missing parameters - {[f'{k}:{input_params[k]}!={task_input[k]}' for k in input_params if input_params[k] != task_input[k]]}"
    if results is not None:
        task_res = task_workflow.output["hatchet_results"]
        assert (
            task_res == results
        ), f"{task_workflow.workflow_name} has different results than expected: {task_res}"
    return task_workflow


async def assert_redis_is_clean(redis_client):
    __tracebackhide__ = False
    non_persistent_keys = await extract_bad_keys_from_redis(redis_client)

    if not non_persistent_keys:
        return

    # Batch all TTL checks in a single pipeline
    async with redis_client.pipeline() as pipe:
        for key in non_persistent_keys:
            pipe.ttl(key)
        ttls = await pipe.execute()

    keys_with_invalid_ttl = [
        (key, ttl)
        for key, ttl in zip(non_persistent_keys, ttls)
        if ttl == -1 or ttl > MAX_DONE_TTL
    ]
    assert (
        len(keys_with_invalid_ttl) == 0
    ), f"Keys without proper TTL (should be <= {MAX_DONE_TTL}s): {keys_with_invalid_ttl}"


def assert_task_was_paused(runs: HatchetRuns, task: TaskSignature, with_resume=False):
    __tracebackhide__ = False  # force pytest to show this frame
    task_id = task.key
    wf_by_task_id = map_wf_by_id(runs, also_not_done=True)

    # Check kwargs were stored
    hatchet_call = wf_by_task_id[task_id]
    assert (
        hatchet_call.status == V1TaskStatus.CANCELLED
    ), f"{task.task_name} was not cancelled ({_task_error_info(hatchet_call)})"
    expected_dump = task.model_validators.model_validate(hatchet_call.input["input"])
    expected_saved_params = expected_dump.model_dump(exclude_unset=True)
    for key, value in expected_saved_params.items():
        assert task.kwargs.get(key) == value, f"{key} != {value}, from {task.task_name}"

    if with_resume:
        wf_by_task_id = map_wf_by_id(runs)
        _assert_task_done(task, wf_by_task_id, None)


def assert_tasks_in_order(wf_by_signature: WF_MAPPING_TYPE, tasks: list[TaskSignature]):
    # Check the task in a chain were called in order
    for i in range(len(tasks) - 1):
        curr_wf = wf_by_signature[tasks[i].key]
        assert (
            curr_wf.status == V1TaskStatus.COMPLETED
        ), f"Task {curr_wf.workflow_name} - {_task_error_info(curr_wf)}"
        next_wf = wf_by_signature[tasks[i + 1].key]
        assert (
            curr_wf.started_at < next_wf.started_at
        ), f"Task {curr_wf.workflow_name} started after {next_wf.workflow_name}"


def assert_signature_not_called(runs: HatchetRuns, task_sign: TaskSignature | str):
    wf_by_signature = map_wf_by_id(runs, also_not_done=True)
    if isinstance(task_sign, TaskSignature):
        task_alias = task_sign.task_name
        task_sign = task_sign.key
    else:
        task_alias = task_sign

    assert task_sign not in wf_by_signature, f"{task_alias} was called"


def assert_swarm_task_done(
    runs: HatchetRuns,
    swarm_task: SwarmTaskSignature,
    tasks: list[TaskSignature],
    allow_fails: bool = True,
    check_callbacks: bool = True,
    swarm_msg: BaseModel = None,
    **swarm_kwargs,
):
    task_map = {task.key: task for task in tasks}

    # Assert for a batch task done as well as extract the wf
    swarm_runs = []
    msg_data = (
        swarm_msg.model_dump(mode="json", exclude_unset=True) if swarm_msg else {}
    )
    for sub_task_id in swarm_task.tasks:
        task = task_map[sub_task_id]
        wf = assert_signature_done(
            runs,
            task,
            check_called_once=False,
            check_finished_once=True,
            allow_fails=allow_fails,
            **(task.kwargs | msg_data | swarm_kwargs),
        )
        swarm_runs.append(wf)

    expected_output = [
        task_output.get("hatchet_results")
        for wf in swarm_runs
        if wf.status == V1TaskStatus.COMPLETED
        if (task_output := wf.output)
        if "hatchet_results" in task_output
    ]

    if check_callbacks:
        for callback_sign in swarm_task.success_callbacks:
            task = task_map[callback_sign]
            callback_wf = assert_signature_done(
                runs, task, check_called_once=True, **task.kwargs
            )
            for result in callback_wf.input["input"]["task_result"]:
                assert (
                    result in expected_output
                ), f"{result} not found in {expected_output} for callback {callback_wf.workflow_name}"

        for error_callback_sign in swarm_task.error_callbacks:
            assert_signature_not_called(runs, error_callback_sign)


def assert_chain_done(
    runs: HatchetRuns,
    chain_signature: ChainTaskSignature,
    full_tasks: list[TaskSignature],
    check_callbacks: bool = True,
    **chain_kwargs,
):
    wf_by_signature = map_wf_by_id(runs)
    task_map = {task.key: task for task in full_tasks}
    chain_tasks = [task_map[task_id] for task_id in chain_signature.tasks]
    assert_tasks_in_order(wf_by_signature, chain_tasks)
    output_value = None
    for chain_task_id in chain_signature.tasks:
        input_params = chain_kwargs.copy()
        task = task_map[chain_task_id]
        if output_value:
            input_params |= {return_value_field(task.model_validators): output_value}
        task_wf = _assert_task_done(task, wf_by_signature, input_params)
        output_value = task_wf.output["hatchet_results"]

    if check_callbacks:
        for chain_success in chain_signature.success_callbacks:
            task = task_map[chain_success]
            input_params = {return_value_field(task.model_validators): output_value}
            _assert_task_done(task, wf_by_signature, input_params)


def assert_paused(
    runs: HatchetRuns,
    tasks: list[TaskSignature],
    start_time: datetime,
    end_time: datetime,
):
    wf_by_task_id = map_wf_by_id(runs, also_not_done=True)
    tasks_map = {task.key: task for task in tasks}
    for task_id, wf in wf_by_task_id.items():
        if task_id not in tasks_map:
            continue
        task_start_time = wf.started_at
        start_time = start_time.astimezone(task_start_time.tzinfo)
        start_before_pause = task_start_time < start_time
        end_time = end_time.astimezone(task_start_time.tzinfo)
        started_after_pause = task_start_time > end_time
        task_was_stopped = is_task_paused(wf)
        assert (
            start_before_pause or started_after_pause or task_was_stopped
        ), f"{wf.workflow_name} was not paused in {task_start_time} ({_task_error_info(wf)})"

    paused_tasks = [wf for wf in wf_by_task_id.values() if is_task_paused(wf)]
    for paused_wf in paused_tasks:
        task_id = get_task_param(paused_wf, TASK_ID_PARAM_NAME)
        task = tasks_map[task_id]
        assert_task_was_paused(runs, task)


def assert_task_did_not_repeat(runs: HatchetRuns):
    task_done = [
        task_id
        for wf in runs
        if (task_id := get_task_param(wf, TASK_ID_PARAM_NAME))
        if is_wf_done(wf)
    ]

    assert len(task_done) == len(set(task_done)), "Task repeated"


def assert_logs_dont_overlap(logs_per_run: list[V1LogLineList]):
    time_windows = []
    for i, log_list in enumerate(logs_per_run):
        if not log_list.rows:
            continue
        timestamps = [line.created_at for line in log_list.rows]
        time_windows.append((min(timestamps), max(timestamps), i))

    time_windows.sort(key=lambda x: x[0])

    for idx in range(len(time_windows) - 1):
        _, end, wf_i = time_windows[idx]
        next_start, _, wf_j = time_windows[idx + 1]
        assert end <= next_start, (
            f"Logs overlap: run {wf_i} ends at {end}, "
            f"run {wf_j} starts at {next_start}"
        )


def assert_overlaps_leq_k_workflows(
    workflows: list[V1TaskSummary], max_concurrency: int = 4
):
    """
    Check workflow concurrency constraints using the sweep line algorithm.
    """
    # Create events for each workflow: (time, delta, workflow_id)
    # delta: +1 for start, -1 for the end
    events = []
    for i, wf in enumerate(workflows):
        events.append((wf.started_at, +1, i))

        # Only add end event if the workflow has finished
        if wf.finished_at is not None:
            events.append((wf.finished_at, -1, i))

    # Sort events by time, with end events before start events for tiebreaking
    # This ensures workflows that end exactly when others start don't count as overlapping
    events.sort(key=lambda x: (x[0], -x[1]))

    active_count = 0
    max_active_seen = 0
    active_workflows = set()  # Track which workflows are currently active

    for time, delta, wf_id in events:
        if delta == +1:
            active_workflows.add(wf_id)
        else:
            active_workflows.discard(wf_id)

        active_count += delta
        max_active_seen = max(max_active_seen, active_count)

        # Check maximum concurrency constraint
        if active_count > max_concurrency:
            active_workflow_names = [
                workflows[wf_id].workflow_name for wf_id in active_workflows
            ]
            assert False, (
                f"Too many workflows running concurrently: {active_count} > {max_concurrency} "
                f"at time {time}. "
                f"Active workflows: {', '.join(active_workflow_names)}"
            )


async def assert_hook_fired(
    redis_client,
    workflow_run_id: str,
    hook_type: str,
) -> None:
    hook_key = f"user-hook-{hook_type}:{workflow_run_id}"
    hook_value = await redis_client.get(hook_key)
    assert hook_value == "fired", f"User {hook_type} hook did not fire (key={hook_key})"


def assert_workflow_run(
    runs: HatchetRuns,
    expected: ExpectedWorkflowRun,
):
    # Find the workflow run (the one with children)
    workflow_runs = [r for r in runs if r.children is not None]
    assert len(workflow_runs) >= 1, "No workflow run found in runs"
    wf_run = workflow_runs[0]

    # Check overall workflow status
    assert (
        wf_run.status == expected.workflow_status
    ), f"Workflow status: expected {expected.workflow_status}, got {wf_run.status}"

    # Check each expected step in children
    assert (
        wf_run.children is not None
    ), "Workflow run has no children, it is not a workflow"
    children_by_name = {child.display_name: child for child in wf_run.children}
    for step in expected.steps:
        if step.status is None:
            assert (
                step.name not in children_by_name
            ), f"Step '{step.name}' should not have been called"
            continue

        assert step.name in children_by_name, (
            f"Step '{step.name}' not found in workflow children. "
            f"Available: {list(children_by_name.keys())}"
        )
        child = children_by_name[step.name]
        assert (
            child.status == step.status
        ), f"Step '{step.name}': expected {step.status}, got {child.status}"
