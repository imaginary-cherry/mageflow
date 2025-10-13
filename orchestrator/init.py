from hatchet_sdk import Hatchet

from orchestrator import register_task
from orchestrator.hatchet.chain import (
    chain_end_task,
    chain_error_task,
    ChainSuccessTaskCommandMessage,
)
from orchestrator.hatchet.swarm import (
    swarm_start_tasks,
    swarm_item_done,
    SwarmItemTaskDoneMessage,
    SwarmTaskCommandMessage,
    swarm_item_failed,
    SwarmItemTaskErrorMessage,
)
from orchestrator.task_name.infrastructure import InfrastructureTasks


def init_hatchet_tasks(hatchet: Hatchet):
    # Chain tasks
    hatchet_chain_done = hatchet.task(
        name=InfrastructureTasks.on_chain_done,
        input_validator=ChainSuccessTaskCommandMessage,
    )
    hatchet_chain_error = hatchet.task(name=InfrastructureTasks.on_chain_error)
    chain_done_task = hatchet_chain_done(chain_end_task)
    on_chain_error_task = hatchet_chain_error(chain_error_task)
    register_chain_done = register_task(InfrastructureTasks.on_chain_done)
    register_chain_error = register_task(InfrastructureTasks.on_chain_error)
    chain_done_task = register_chain_done(chain_done_task)
    on_chain_error_task = register_chain_error(on_chain_error_task)

    # Swarm tasks
    swarm_start = hatchet.task(
        name=InfrastructureTasks.on_swarm_start,
        input_validator=SwarmTaskCommandMessage,
    )
    swarm_done = hatchet.task(
        name=InfrastructureTasks.on_swarm_done,
        input_validator=SwarmItemTaskDoneMessage,
    )
    swarm_error = hatchet.task(
        name=InfrastructureTasks.on_swarm_error,
        input_validator=SwarmItemTaskErrorMessage,
    )
    swarm_start = swarm_start(swarm_start_tasks)
    swarm_done = swarm_done(swarm_item_done)
    swarm_error = swarm_error(swarm_item_failed)
    register_swarm_start = register_task(InfrastructureTasks.on_swarm_start)
    register_swarm_done = register_task(InfrastructureTasks.on_swarm_done)
    register_swarm_error = register_task(InfrastructureTasks.on_swarm_error)
    swarm_start = register_swarm_start(swarm_start)
    swarm_done = register_swarm_done(swarm_done)
    swarm_error = register_swarm_error(swarm_error)

    return [
        on_chain_error_task,
        chain_done_task,
        swarm_start,
        swarm_done,
        swarm_error,
    ]
