import os
import logging

# Start coverage if COVERAGE_PROCESS_START is set
if os.environ.get("COVERAGE_PROCESS_START"):
    try:
        import coverage

        coverage.process_startup()
    except ImportError:
        pass

import redis
from dynaconf import Dynaconf
from hatchet_sdk import Hatchet, ClientConfig, Context
from hatchet_sdk.config import HealthcheckConfig

import mageflow
from tests.integration.models import (
    ContextMessage,
    CommandMessageWithResult,
    MageflowTestError,
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


@hatchet.task(name="mcp-task1", input_validator=ContextMessage)
def task1(msg):
    return "msg"


@hatchet.task(name="mcp-task2", input_validator=ContextMessage)
def task2(msg):
    return msg


@hatchet.task(name="mcp-task3", input_validator=ContextMessage)
def task3(msg):
    return 2


@hatchet.durable_task(name="mcp-chain-callback", input_validator=CommandMessageWithResult)
def chain_callback(msg):
    return msg


@hatchet.task(name="mcp-fail-task", input_validator=ContextMessage)
def fail_task(msg):
    raise MageflowTestError("Test exception")


LOG_LINE_1 = "Hello from logging task"
LOG_LINE_2 = "Processing complete"


@hatchet.task(name="mcp-logging-task", input_validator=ContextMessage)
@hatchet.with_ctx
def logging_task(msg, ctx: Context):
    ctx.log(LOG_LINE_1)
    ctx.log(LOG_LINE_2)
    return "logged"


workflows = [task1, task2, task3, chain_callback, fail_task, logging_task]


def main() -> None:
    worker = hatchet.worker("mcp-tests", workflows=workflows)
    worker.start()


if __name__ == "__main__":
    main()
