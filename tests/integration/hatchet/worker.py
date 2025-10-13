import asyncio
import json
from typing import Any, Annotated

from hatchet_sdk import Hatchet, ClientConfig
from hatchet_sdk.config import HealthcheckConfig

import orchestrator
from orchestrator import ReturnValue
from orchestrator.initialization import lifespan_initialize

settings = load_settings()
config_obj = ClientConfig(
    token=settings.hatchet.api_key,
    tls_strategy="none",
    namespace=settings.hatchet.namespace,
    healthcheck=HealthcheckConfig(enabled=True),
)

hatchet = Hatchet(debug=True, config=config_obj)


class CommandMessageWithResult(orchestrator.CommandTaskMessage):
    task_result: Annotated[Any, ReturnValue()]


# > Default priority
DEFAULT_PRIORITY = 1
SLEEP_TIME = 0.25


@orchestrator.register_task("task1-test")
@hatchet.task(name="task1", input_validator=orchestrator.CommandTaskMessage)
@orchestrator.handle_task_callback()
def task1(msg):
    return f"msg"


@orchestrator.register_task("task1-callback")
@hatchet.task(name="task1_callback", input_validator=orchestrator.CommandTaskMessage)
@orchestrator.handle_task_callback()
def task1_callback(msg):
    return msg


@orchestrator.register_task("error-callback")
@hatchet.task(name="error_callback", input_validator=orchestrator.CommandTaskMessage)
@orchestrator.handle_task_callback()
def error_callback(msg):
    print(msg)


@orchestrator.register_task("task2-test")
@hatchet.task(name="task2", input_validator=orchestrator.CommandTaskMessage)
@orchestrator.handle_task_callback()
def task2(msg):
    return msg


@orchestrator.register_task("task3-test")
@hatchet.task(name="task3", input_validator=orchestrator.CommandTaskMessage)
@orchestrator.handle_task_callback()
def task3(msg):
    return 2


@orchestrator.register_task("chain-callback-test")
@hatchet.task(name="chain_callback", input_validator=orchestrator.CommandTaskMessage)
@orchestrator.handle_task_callback()
def chain_callback(msg):
    return msg


@orchestrator.register_task("fail-task")
@hatchet.task(name="fail_task", input_validator=orchestrator.CommandTaskMessage)
@orchestrator.handle_task_callback()
def fail_task(msg):
    raise ValueError("Test exception")


@orchestrator.register_task("sleep-task")
@hatchet.task(name="sleep_task", input_validator=orchestrator.CommandTaskMessage)
@orchestrator.handle_task_callback()
def sleep_task(msg):
    import time

    time.sleep(2)
    return msg


@orchestrator.register_task("callback-with-redis")
@hatchet.task(name="callback_with_redis", input_validator=CommandMessageWithResult)
@orchestrator.handle_task_callback()
async def callback_with_redis(msg: CommandMessageWithResult):
    from orchestrator.hatchet.config import orchestrator_config

    await orchestrator_config.redis_client.set(
        f"activated-task-{msg.metadata.task_id}", json.dumps(msg.task_result)
    )
    return msg


orchestrator_tasks = orchestrator.init_hatchet_tasks(hatchet)
workflows = [
    task1,
    task2,
    task3,
    chain_callback,
    task1_callback,
    fail_task,
    error_callback,
    sleep_task,
    callback_with_redis,
] + orchestrator_tasks


def main() -> None:
    asyncio.run(orchestrator.init_from_dynaconf(workflows))

    worker = hatchet.worker(
        "orchestrator-test",
        workflows=workflows,
        lifespan=lifespan_initialize,
    )

    worker.start()


if __name__ == "__main__":
    main()
