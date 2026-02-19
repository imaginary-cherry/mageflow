from datetime import timedelta

from hatchet_sdk import Hatchet
from hatchet_sdk.runnables.types import ConcurrencyExpression, ConcurrencyLimitStrategy

from mageflow.clients.inner_task_names import (
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
        concurrency=[
            ConcurrencyExpression(
                expression=f"input.{SWARM_TASK_ID_PARAM_NAME}",
                max_runs=2,
                limit_strategy=ConcurrencyLimitStrategy.CANCEL_NEWEST,
            ),
            ConcurrencyExpression(
                expression=f"input.{SWARM_TASK_ID_PARAM_NAME}",
                max_runs=1,
                limit_strategy=ConcurrencyLimitStrategy.GROUP_ROUND_ROBIN,
            ),
        ],
    )
    swarm_fill_task = swarm_fill_task(fill_swarm_running_tasks)

    return [
        swarm_done,
        swarm_error,
        swarm_fill_task,
    ]
