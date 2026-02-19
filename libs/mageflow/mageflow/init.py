from datetime import timedelta

from hatchet_sdk import Hatchet
from hatchet_sdk.runnables.types import ConcurrencyExpression, ConcurrencyLimitStrategy

from mageflow.chain.messages import ChainCallbackMessage, ChainErrorMessage
from mageflow.chain.workflows import chain_end_task, chain_error_task
from mageflow.clients.inner_task_names import (
    ON_CHAIN_END,
    ON_CHAIN_ERROR,
    ON_SWARM_ITEM_DONE,
    SWARM_FILL_TASK,
    ON_SWARM_ITEM_ERROR,
)
from mageflow.swarm.consts import SWARM_TASK_ID_PARAM_NAME
from mageflow.swarm.messages import (
    SwarmResultsMessage,
    SwarmErrorMessage,
    FillSwarmMessage,
)
from mageflow.swarm.workflows import (
    swarm_item_failed,
    swarm_item_done,
    fill_swarm_running_tasks,
)


def init_mageflow_hatchet_tasks(hatchet: Hatchet):
    # Chain tasks
    hatchet_chain_done = hatchet.durable_task(
        name=ON_CHAIN_END,
        input_validator=ChainCallbackMessage,
        retries=3,
        execution_timeout=timedelta(minutes=5),
    )
    hatchet_chain_error = hatchet.durable_task(
        name=ON_CHAIN_ERROR,
        input_validator=ChainErrorMessage,
        retries=3,
        execution_timeout=timedelta(minutes=5),
    )
    chain_done_task = hatchet_chain_done(chain_end_task)
    on_chain_error_task = hatchet_chain_error(chain_error_task)

    # Swarm tasks
    swarm_done = hatchet.durable_task(
        name=ON_SWARM_ITEM_DONE,
        input_validator=SwarmResultsMessage,
        retries=5,
        execution_timeout=timedelta(minutes=1),
    )
    swarm_error = hatchet.durable_task(
        name=ON_SWARM_ITEM_ERROR,
        input_validator=SwarmErrorMessage,
        retries=5,
        execution_timeout=timedelta(minutes=5),
    )
    swarm_done = swarm_done(swarm_item_done)
    swarm_error = swarm_error(swarm_item_failed)

    swarm_fill_task = hatchet.durable_task(
        name=SWARM_FILL_TASK,
        input_validator=FillSwarmMessage,
        execution_timeout=timedelta(minutes=5),
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
        swarm_done,
        swarm_error,
        swarm_fill_task,
    ]
