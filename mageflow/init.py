from datetime import timedelta

from hatchet_sdk import Hatchet
from hatchet_sdk.runnables.types import ConcurrencyExpression, ConcurrencyLimitStrategy

from mageflow.callbacks import register_task
from mageflow.chain.consts import ON_CHAIN_END, ON_CHAIN_ERROR
from mageflow.chain.messages import ChainCallbackMessage
from mageflow.chain.workflows import chain_end_task, chain_error_task
from mageflow.swarm.consts import (
    ON_SWARM_ERROR,
    ON_SWARM_END,
    ON_SWARM_START,
    SWARM_ITEM_TASK_ID_PARAM_NAME,
    SWARM_FILL_TASK,
    SWARM_TASK_ID_PARAM_NAME,
)
from mageflow.swarm.messages import SwarmResultsMessage, SwarmMessage
from mageflow.swarm.workflows import (
    swarm_item_failed,
    swarm_item_done,
    swarm_start_tasks,
    fill_swarm_running_tasks,
)


def init_mageflow_hatchet_tasks(hatchet: Hatchet):
    # Chain tasks
    hatchet_chain_done = hatchet.task(
        name=ON_CHAIN_END,
        input_validator=ChainCallbackMessage,
        retries=3,
        execution_timeout=timedelta(minutes=5),
    )
    hatchet_chain_error = hatchet.task(
        name=ON_CHAIN_ERROR,
        retries=3,
        execution_timeout=timedelta(minutes=5),
    )
    chain_done_task = hatchet_chain_done(chain_end_task)
    on_chain_error_task = hatchet_chain_error(chain_error_task)
    register_chain_done = register_task(ON_CHAIN_END)
    register_chain_error = register_task(ON_CHAIN_ERROR)
    chain_done_task = register_chain_done(chain_done_task)
    on_chain_error_task = register_chain_error(on_chain_error_task)

    # Swarm tasks
    swarm_start = hatchet.durable_task(
        name=ON_SWARM_START,
        retries=3,
        execution_timeout=timedelta(minutes=5),
        concurrency=ConcurrencyExpression(
            expression=f"input.{SWARM_ITEM_TASK_ID_PARAM_NAME}",
            max_runs=1,
            limit_strategy=ConcurrencyLimitStrategy.CANCEL_NEWEST,
        ),
    )
    swarm_done = hatchet.durable_task(
        name=ON_SWARM_END,
        input_validator=SwarmResultsMessage,
        retries=5,
        execution_timeout=timedelta(minutes=1),
    )
    swarm_error = hatchet.durable_task(
        name=ON_SWARM_ERROR, retries=5, execution_timeout=timedelta(minutes=5)
    )
    swarm_start = swarm_start(swarm_start_tasks)
    swarm_done = swarm_done(swarm_item_done)
    swarm_error = swarm_error(swarm_item_failed)
    register_swarm_start = register_task(ON_SWARM_START)
    register_swarm_done = register_task(ON_SWARM_END)
    register_swarm_error = register_task(ON_SWARM_ERROR)
    swarm_start = register_swarm_start(swarm_start)
    swarm_done = register_swarm_done(swarm_done)
    swarm_error = register_swarm_error(swarm_error)

    swarm_fill_task = hatchet.durable_task(
        name=SWARM_FILL_TASK,
        input_validator=SwarmMessage,
        retries=4,
        concurrency=ConcurrencyExpression(
            expression=f"input.{SWARM_TASK_ID_PARAM_NAME}",
            max_runs=2,
            limit_strategy=ConcurrencyLimitStrategy.CANCEL_NEWEST,
        ),
    )
    swarm_fill_task = swarm_fill_task(fill_swarm_running_tasks)

    return [
        on_chain_error_task,
        chain_done_task,
        swarm_start,
        swarm_done,
        swarm_error,
        swarm_fill_task,
    ]
