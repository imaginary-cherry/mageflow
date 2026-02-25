import asyncio
import json
import logging
import os
from datetime import datetime, timedelta

from thirdmagic.consts import TASK_ID_PARAM_NAME
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
from hatchet_sdk import Hatchet, ClientConfig, Context, NonRetryableException
from hatchet_sdk.config import HealthcheckConfig

import mageflow
from tests.integration.hatchet.models import (
    ContextMessage,
    MessageWithData,
    MessageWithResult,
    CommandMessageWithResult,
    SleepTaskMessage,
    MageflowTestError,
    MessageWithMsgResults,
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
hatchet = mageflow.Mageflow(hatchet, redis_client=redis)

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
async def retry_to_failure(msg, signature: TaskSignature):
    await TaskSignature.Meta.redis.set(
        f"finish-{signature.key}", datetime.now().isoformat()
    )
    raise ValueError("Test exception")


@hatchet.task(
    retries=3, execution_timeout=timedelta(seconds=60), input_validator=ContextMessage
)
async def cancel_retry(msg):
    raise NonRetryableException("Test exception")


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
    retry_once,
    normal_retry_once,
    retry_to_failure,
    cancel_retry,
]


async def lifespan():
    print("HI")
    yield


def main() -> None:
    worker = hatchet.worker("tests", workflows=workflows, lifespan=lifespan)

    worker.start()


if __name__ == "__main__":
    main()
