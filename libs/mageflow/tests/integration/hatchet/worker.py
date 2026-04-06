import asyncio
import json
import logging
import os
from datetime import datetime, timedelta

from thirdmagic.consts import REMOVED_TASK_TTL, TASK_ID_PARAM_NAME
from thirdmagic.task import TaskSignature

# Start coverage if COVERAGE_PROCESS_START is set
if os.environ.get("COVERAGE_PROCESS_START"):
    try:
        import coverage

        coverage.process_startup()
    except ImportError:
        # Coverage not installed, skip subprocess coverage
        pass

import redis
from dynaconf import Dynaconf
from hatchet_sdk import ClientConfig, Context, Hatchet, NonRetryableException
from hatchet_sdk.config import HealthcheckConfig

import mageflow
from mageflow import MageflowConfig, SignatureTTLConfig, TTLConfig
from tests.integration.hatchet.models import (
    CacheIsolationMessage,
    CommandMessageWithResult,
    ContextMessage,
    DagStep3Result,
    DagStepResult,
    MageflowTestError,
    MessageWithData,
    MessageWithMsgResults,
    MessageWithResult,
    SignatureKeysResult,
    SignatureKeyWithWF,
    SleepTaskMessage,
    WorkflowTestMessage,
)

settings = Dynaconf(
    envvar_prefix="DYNACONF",
    settings_files=["settings.toml", ".secrets.toml"],
)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
config_obj = ClientConfig(
    token=settings.hatchet.api_key,
    **settings.hatchet.to_dict(),
    healthcheck=HealthcheckConfig(enabled=True),
    logger=logger,
)

redis = redis.asyncio.from_url(settings.redis.url, decode_responses=True)
hatchet = Hatchet(debug=True, config=config_obj)

# Per-type TTL configuration for tests
TASK_ACTIVE_TTL = 600  # 10 minutes
TASK_DONE_TTL = REMOVED_TASK_TTL + 60  # 1 minute
CHAIN_ACTIVE_TTL = 900  # 15 minutes
CHAIN_DONE_TTL = REMOVED_TASK_TTL + 90  # 1.5 minutes
SWARM_ACTIVE_TTL = 1200  # 20 minutes
SWARM_DONE_TTL = REMOVED_TASK_TTL + 120  # 2 minutes
MAX_DONE_TTL = max(TASK_DONE_TTL, CHAIN_DONE_TTL, SWARM_DONE_TTL)

TEST_MAGEFLOW_CONFIG = MageflowConfig(
    ttl=TTLConfig(
        task=SignatureTTLConfig(
            active_ttl=TASK_ACTIVE_TTL, ttl_when_sign_done=TASK_DONE_TTL
        ),
        chain=SignatureTTLConfig(
            active_ttl=CHAIN_ACTIVE_TTL, ttl_when_sign_done=CHAIN_DONE_TTL
        ),
        swarm=SignatureTTLConfig(
            active_ttl=SWARM_ACTIVE_TTL, ttl_when_sign_done=SWARM_DONE_TTL
        ),
    )
)

hatchet = mageflow.Mageflow(hatchet, redis_client=redis, config=TEST_MAGEFLOW_CONFIG)

# > Default priority
DEFAULT_PRIORITY = 1
SLEEP_TIME = 0.25

task1_test_reg_name = "task1-test"


@hatchet.task(name=task1_test_reg_name, input_validator=ContextMessage)
def task1(msg):
    return f"msg"


@hatchet.durable_task(name="task1_callback", input_validator=CommandMessageWithResult)
def task1_callback(msg):
    return msg


@hatchet.task(name="error_callback", input_validator=ContextMessage)
def error_callback(msg: ContextMessage):
    print(msg)


@hatchet.task(name="task2", input_validator=ContextMessage)
def task2(msg):
    return msg


@hatchet.task(name="accept_msg_results", input_validator=MessageWithMsgResults)
async def accept_msg_results(msg: MessageWithMsgResults):
    return msg


@hatchet.task(name="task-with-data", input_validator=MessageWithData)
def task_with_data(msg):
    return msg.data


@hatchet.task(name="task2-with-res", input_validator=MessageWithResult)
def task2_with_result(msg: MessageWithResult):
    return msg.mageflow_results


@hatchet.task(name="task3", input_validator=ContextMessage)
def task3(msg):
    return 2


@hatchet.task(name="chain_callback", input_validator=ContextMessage)
def chain_callback(msg):
    return msg


@hatchet.task(name="fail_task", input_validator=ContextMessage)
def fail_task(msg):
    raise MageflowTestError("Test exception")


@hatchet.durable_task(name="sleep_task", input_validator=SleepTaskMessage)
async def sleep_task(msg: SleepTaskMessage):
    await asyncio.sleep(msg.sleep_time)
    return msg


@hatchet.task(name="callback_with_redis", input_validator=CommandMessageWithResult)
@hatchet.with_ctx
async def callback_with_redis(msg: CommandMessageWithResult, ctx: Context):
    task_id = ctx.additional_metadata[TASK_ID_PARAM_NAME]

    await TaskSignature.Meta.redis.set(
        f"activated-task-{task_id}", json.dumps(msg.task_result)
    )
    return msg


@hatchet.task(name="return-multiple-values", input_validator=MessageWithResult)
def return_multiple_values(msg):
    return [msg, msg, msg]


@hatchet.task(execution_timeout=timedelta(seconds=1), input_validator=ContextMessage)
async def timeout_task(msg: ContextMessage):
    await asyncio.sleep(10)


@hatchet.task(
    execution_timeout=timedelta(seconds=3), input_validator=ContextMessage, retries=2
)
@hatchet.with_ctx
@hatchet.with_signature
async def retry_timeout_task(
    msg: ContextMessage, ctx: Context, signature: TaskSignature
):
    await TaskSignature.Meta.redis.set(
        f"finish-{signature.key}-{ctx.attempt_number}", datetime.now().isoformat()
    )
    await asyncio.sleep(10)


@hatchet.task(
    retries=3, execution_timeout=timedelta(seconds=60), input_validator=ContextMessage
)
@hatchet.with_ctx
async def retry_once(msg, ctx: Context):
    if ctx.attempt_number == 1:
        raise ValueError("Test exception")
    return "Nice"


@hatchet.task(
    retries=3, execution_timeout=timedelta(seconds=60), input_validator=ContextMessage
)
@hatchet.with_ctx
async def normal_retry_once(msg, ctx: Context):
    if ctx.attempt_number == 1:
        raise ValueError("Test exception")
    return msg


@hatchet.task(
    retries=3, execution_timeout=timedelta(seconds=60), input_validator=ContextMessage
)
@hatchet.with_signature
@hatchet.with_ctx
async def retry_to_failure(msg, ctx: Context, signature: TaskSignature):
    await TaskSignature.Meta.redis.set(
        f"finish-{signature.key}-{ctx.attempt_number}", datetime.now().isoformat()
    )
    raise ValueError("Test exception")


@hatchet.task(
    retries=3, execution_timeout=timedelta(seconds=60), input_validator=ContextMessage
)
async def cancel_retry(msg):
    raise NonRetryableException("Test exception")


@hatchet.durable_task(
    name="create_signatures_for_ttl_test", input_validator=ContextMessage
)
async def create_signatures_for_ttl_test(msg: ContextMessage) -> SignatureKeysResult:
    # Standalone task signature
    task_sig = await hatchet.asign(task1)

    # Chain with pre-created sub-tasks
    chain_sub1 = await hatchet.asign(task1)
    chain_sub2 = await hatchet.asign(task2)
    chain_sig = await hatchet.achain([chain_sub1, chain_sub2])

    # Swarm with pre-created sub-tasks
    swarm_sub1 = await hatchet.asign(task1)
    swarm_sub2 = await hatchet.asign(task2)
    swarm_sig = await hatchet.aswarm([swarm_sub1, swarm_sub2], is_swarm_closed=True)

    return SignatureKeysResult(
        task_keys=[task_sig.key],
        chain_key=chain_sig.key,
        chain_sub_task_keys=[chain_sub1.key, chain_sub2.key],
        swarm_key=swarm_sig.key,
        swarm_sub_task_keys=[swarm_sub1.key, swarm_sub2.key],
        publish_state_key=swarm_sig.publishing_state_id,
    )


@hatchet.durable_task(
    name="retry_cache_durable_task",
    input_validator=ContextMessage,
    retries=3,
    execution_timeout=timedelta(seconds=60),
)
@hatchet.with_ctx
async def retry_cache_durable_task(
    msg: ContextMessage, ctx: Context
) -> SignatureKeyWithWF:
    # Create standalone task signatures
    sig1 = await hatchet.asign(task1)
    sig2 = await hatchet.asign(task2)

    # Create a chain
    chain_sub1 = await hatchet.asign(task1)
    chain_sub2 = await hatchet.asign(task2)
    chain_sig = await hatchet.achain([chain_sub1, chain_sub2])

    # Create a swarm
    swarm_sub1 = await hatchet.asign(task1)
    swarm_sub2 = await hatchet.asign(task2)
    swarm_sig = await hatchet.aswarm([swarm_sub1, swarm_sub2], is_swarm_closed=True)

    # Collect all created signature keys
    results = SignatureKeyWithWF(
        task_keys=[sig1.key, sig2.key],
        chain_key=chain_sig.key,
        chain_sub_task_keys=[chain_sub1.key, chain_sub2.key],
        swarm_key=swarm_sig.key,
        swarm_sub_task_keys=[swarm_sub1.key, swarm_sub2.key],
        publish_state_key=swarm_sig.publishing_state_id,
        workflow_run_id=ctx.workflow_run_id,
    )
    all_keys = results.model_dump(mode="json")

    # Store keys in Redis for test verification, keyed by attempt number
    attempt_key = f"retry-cache-test:{ctx.workflow_run_id}:attempt-{ctx.attempt_number}"
    await TaskSignature.Meta.redis.json().set(attempt_key, "$", all_keys)  # type: ignore[misc]

    if ctx.attempt_number == 1:
        raise ValueError("Intentional first attempt failure for retry cache test")

    new_task = await hatchet.asign(task2)
    results.task_keys.append(new_task.key)

    return results


@hatchet.durable_task(
    name="concurrent_cache_isolation_task",
    input_validator=CacheIsolationMessage,
    retries=3,
    execution_timeout=timedelta(seconds=60),
)
async def concurrent_cache_isolation_task(msg: CacheIsolationMessage):
    # Create a number of signatures based on the message — each run instance
    # sends a different count so we can verify the caches are distinct
    tasks = [task1, task2, task3]
    task_keys = []
    for i in range(msg.sig_count):
        sig = await hatchet.asign(tasks[i % len(tasks)])
        task_keys.append(sig.key)


# --- DAG workflows (message-driven failure behavior) ---

test_dag_wf = hatchet.workflow(name="test-dag-wf", input_validator=WorkflowTestMessage)


@test_dag_wf.task(retries=3, execution_timeout=timedelta(seconds=3))
@hatchet.with_ctx
async def dag_step1(input: WorkflowTestMessage, ctx: Context) -> DagStepResult:
    await input.apply_step_behavior(1, ctx.attempt_number)
    return DagStepResult(step="1")


@test_dag_wf.task(retries=3, execution_timeout=timedelta(seconds=3))
@hatchet.with_ctx
async def dag_step2(input: WorkflowTestMessage, ctx: Context) -> DagStepResult:
    await input.apply_step_behavior(2, ctx.attempt_number)
    return DagStepResult(step="2")


@test_dag_wf.task(
    parents=[dag_step1, dag_step2],
    retries=3,
    execution_timeout=timedelta(seconds=3),
)
@hatchet.with_ctx
async def dag_step3(input: WorkflowTestMessage, ctx: Context) -> DagStep3Result:
    await input.apply_step_behavior(3, ctx.attempt_number)
    one = ctx.task_output(dag_step1)
    two = ctx.task_output(dag_step2)
    return DagStep3Result(
        step="3", parent_results=[DagStepResult(**one), DagStepResult(**two)]
    )


test_dag_wf_hooks = hatchet.workflow(
    name="test-dag-wf-hooks", input_validator=WorkflowTestMessage
)


@test_dag_wf_hooks.task(retries=3, execution_timeout=timedelta(seconds=3))
@hatchet.with_ctx
async def dag_hooks_step1(input: WorkflowTestMessage, ctx: Context) -> DagStepResult:
    await input.apply_step_behavior(1, ctx.attempt_number)
    return DagStepResult(step="1")


@test_dag_wf_hooks.task(
    parents=[dag_hooks_step1],
    retries=3,
    execution_timeout=timedelta(seconds=3),
)
@hatchet.with_ctx
async def dag_hooks_step2(input: WorkflowTestMessage, ctx: Context) -> DagStepResult:
    await input.apply_step_behavior(2, ctx.attempt_number)
    return DagStepResult(step="2")


@test_dag_wf_hooks.on_success_task()
async def dag_hooks_on_success(input, ctx: Context):
    if hasattr(input, "fail_at_on_success") and input.fail_at_on_success:
        raise MageflowTestError("on_success hook failed")
    await TaskSignature.Meta.redis.set(
        f"user-hook-success:{ctx.workflow_run_id}", "fired"
    )


@test_dag_wf_hooks.on_failure_task()
async def dag_hooks_on_failure(input, ctx: Context):
    if hasattr(input, "fail_at_on_failure") and input.fail_at_on_failure:
        raise MageflowTestError("on_failure hook failed")
    await TaskSignature.Meta.redis.set(
        f"user-hook-failure:{ctx.workflow_run_id}", "fired"
    )


workflows = [
    task1,
    task2,
    task_with_data,
    task2_with_result,
    task3,
    chain_callback,
    task1_callback,
    fail_task,
    error_callback,
    sleep_task,
    callback_with_redis,
    return_multiple_values,
    timeout_task,
    retry_timeout_task,
    retry_once,
    normal_retry_once,
    retry_to_failure,
    cancel_retry,
    accept_msg_results,
    create_signatures_for_ttl_test,
    retry_cache_durable_task,
    concurrent_cache_isolation_task,
    test_dag_wf,
    test_dag_wf_hooks,
]


async def lifespan():
    print("HI")
    yield


def main() -> None:
    worker = hatchet.worker("tests", workflows=workflows, lifespan=lifespan)

    worker.start()


if __name__ == "__main__":
    main()
