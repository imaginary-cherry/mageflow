"""
TaskIQ-specific framework task definitions.

This module creates the internal framework tasks (chain, swarm handlers)
using TaskIQ's specific API.

NOTE: This is a skeleton. The actual implementation depends on your
TaskIQ setup and how you want to handle chain/swarm functionality.
"""
from typing import TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from mageflow.adapters.taskiq.adapter import TaskIQAdapter

logger = logging.getLogger(__name__)


def create_taskiq_framework_tasks(adapter: "TaskIQAdapter") -> list:
    """
    Create internal framework tasks for TaskIQ.

    This function creates and registers the internal tasks needed for
    chain and swarm functionality using TaskIQ's task registration.

    The chain/swarm workflows need to be adapted for TaskIQ's model:
    - No ctx parameter (use message for metadata)
    - Different logging mechanism
    - Different task triggering API

    Args:
        adapter: TaskIQAdapter instance

    Returns:
        List of registered task objects
    """
    from mageflow.chain.consts import ON_CHAIN_END, ON_CHAIN_ERROR
    from mageflow.swarm.consts import (
        ON_SWARM_ERROR,
        ON_SWARM_END,
        ON_SWARM_START,
        SWARM_FILL_TASK,
    )

    # Create TaskIQ-compatible versions of the framework tasks
    # These wrappers adapt the workflow functions to work without ctx

    @adapter.task(name=ON_CHAIN_END)
    async def taskiq_chain_end_task(msg: dict):
        """Chain completion handler for TaskIQ."""
        from mageflow.adapters.taskiq.workflow_handlers import handle_chain_end

        return await handle_chain_end(msg, adapter)

    @adapter.task(name=ON_CHAIN_ERROR)
    async def taskiq_chain_error_task(msg: dict):
        """Chain error handler for TaskIQ."""
        from mageflow.adapters.taskiq.workflow_handlers import handle_chain_error

        return await handle_chain_error(msg, adapter)

    @adapter.durable_task(name=ON_SWARM_START)
    async def taskiq_swarm_start_tasks(msg: dict):
        """Swarm start handler for TaskIQ."""
        from mageflow.adapters.taskiq.workflow_handlers import handle_swarm_start

        return await handle_swarm_start(msg, adapter)

    @adapter.durable_task(name=ON_SWARM_END)
    async def taskiq_swarm_item_done(msg: dict):
        """Swarm item completion handler for TaskIQ."""
        from mageflow.adapters.taskiq.workflow_handlers import handle_swarm_item_done

        return await handle_swarm_item_done(msg, adapter)

    @adapter.durable_task(name=ON_SWARM_ERROR)
    async def taskiq_swarm_item_failed(msg: dict):
        """Swarm item failure handler for TaskIQ."""
        from mageflow.adapters.taskiq.workflow_handlers import handle_swarm_item_failed

        return await handle_swarm_item_failed(msg, adapter)

    @adapter.durable_task(name=SWARM_FILL_TASK)
    async def taskiq_fill_swarm_running_tasks(msg: dict):
        """Swarm fill handler for TaskIQ."""
        from mageflow.adapters.taskiq.workflow_handlers import handle_swarm_fill

        return await handle_swarm_fill(msg, adapter)

    return [
        taskiq_chain_end_task,
        taskiq_chain_error_task,
        taskiq_swarm_start_tasks,
        taskiq_swarm_item_done,
        taskiq_swarm_item_failed,
        taskiq_fill_swarm_running_tasks,
    ]
