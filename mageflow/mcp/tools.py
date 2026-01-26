"""MCP tool implementations for MageFlow task inspection."""

import asyncio
from typing import Optional

from mageflow.signature.model import TaskSignature
from mageflow.signature.status import SignatureStatus
from mageflow.chain.model import ChainTaskSignature
from mageflow.swarm.model import SwarmTaskSignature, BatchItemTaskSignature
from mageflow.mcp.types import (
    TaskInfo,
    CallbackInfo,
    CallbacksResponse,
    ChainTaskInfo,
    ChainTasksResponse,
    ChainStatusResponse,
    SwarmTaskInfo,
    SwarmTasksResponse,
    SwarmStatusResponse,
    TaskGraphNode,
)


def _get_task_type(task: TaskSignature) -> str:
    """Get the task type name."""
    return type(task).__name__


def _format_datetime(dt) -> Optional[str]:
    """Format datetime to ISO string."""
    if dt is None:
        return None
    try:
        return dt.isoformat()
    except Exception:
        return str(dt)


async def get_task(task_id: str) -> Optional[TaskInfo]:
    """
    Get complete task information by ID.

    Args:
        task_id: The task identifier (e.g., "TaskSignature:abc123...")

    Returns:
        TaskInfo with all task details, or None if not found
    """
    task = await TaskSignature.get_safe(task_id)
    if task is None:
        return None

    kwargs = {}
    try:
        kwargs = dict(task.kwargs) if task.kwargs else {}
    except Exception:
        pass

    identifiers = {}
    try:
        identifiers = dict(task.task_identifiers) if task.task_identifiers else {}
    except Exception:
        pass

    creation_time = None
    try:
        creation_time = _format_datetime(task.creation_time)
    except Exception:
        pass

    return TaskInfo(
        task_id=task.key,
        task_type=_get_task_type(task),
        task_name=task.task_name,
        status=task.task_status.status.value,
        last_status=task.task_status.last_status.value,
        worker_task_id=task.task_status.worker_task_id or "",
        creation_time=creation_time,
        kwargs=kwargs,
        task_identifiers=identifiers,
        success_callbacks_count=len(task.success_callbacks),
        error_callbacks_count=len(task.error_callbacks),
    )


async def get_task_callbacks(
    task_id: str,
    include_success: bool = True,
    include_error: bool = True,
) -> Optional[CallbacksResponse]:
    """
    Get success and/or error callbacks of a task.

    Args:
        task_id: The task identifier
        include_success: Whether to include success callbacks
        include_error: Whether to include error callbacks

    Returns:
        CallbacksResponse with callback details, or None if task not found
    """
    task = await TaskSignature.get_safe(task_id)
    if task is None:
        return None

    success_callbacks = []
    error_callbacks = []

    if include_success and task.success_callbacks:
        callback_tasks = await asyncio.gather(
            *[TaskSignature.get_safe(cb_id) for cb_id in task.success_callbacks],
            return_exceptions=True,
        )
        for cb_task in callback_tasks:
            if isinstance(cb_task, TaskSignature):
                kwargs = {}
                try:
                    kwargs = dict(cb_task.kwargs) if cb_task.kwargs else {}
                except Exception:
                    pass
                success_callbacks.append(
                    CallbackInfo(
                        task_id=cb_task.key,
                        task_name=cb_task.task_name,
                        status=cb_task.task_status.status.value,
                        kwargs=kwargs,
                    )
                )

    if include_error and task.error_callbacks:
        callback_tasks = await asyncio.gather(
            *[TaskSignature.get_safe(cb_id) for cb_id in task.error_callbacks],
            return_exceptions=True,
        )
        for cb_task in callback_tasks:
            if isinstance(cb_task, TaskSignature):
                kwargs = {}
                try:
                    kwargs = dict(cb_task.kwargs) if cb_task.kwargs else {}
                except Exception:
                    pass
                error_callbacks.append(
                    CallbackInfo(
                        task_id=cb_task.key,
                        task_name=cb_task.task_name,
                        status=cb_task.task_status.status.value,
                        kwargs=kwargs,
                    )
                )

    return CallbacksResponse(
        task_id=task_id,
        success_callbacks=success_callbacks,
        error_callbacks=error_callbacks,
    )


async def get_task_graph(
    task_id: str,
    max_depth: int = 5,
    include_callbacks: bool = True,
) -> Optional[TaskGraphNode]:
    """
    Get the full task graph recursively.

    Args:
        task_id: The root task identifier
        max_depth: Maximum recursion depth (default: 5)
        include_callbacks: Whether to include callback graphs

    Returns:
        TaskGraphNode representing the task tree, or None if not found
    """

    async def build_node(tid: str, depth: int) -> Optional[TaskGraphNode]:
        if depth > max_depth:
            return None

        task = await TaskSignature.get_safe(tid)
        if task is None:
            return None

        children = []
        success_cb_nodes = []
        error_cb_nodes = []

        # Get children based on task type
        if isinstance(task, ChainTaskSignature):
            child_tasks = await asyncio.gather(
                *[build_node(child_id, depth + 1) for child_id in task.tasks],
                return_exceptions=True,
            )
            children = [c for c in child_tasks if isinstance(c, TaskGraphNode)]

        elif isinstance(task, SwarmTaskSignature):
            child_tasks = await asyncio.gather(
                *[build_node(child_id, depth + 1) for child_id in task.tasks],
                return_exceptions=True,
            )
            children = [c for c in child_tasks if isinstance(c, TaskGraphNode)]

        elif isinstance(task, BatchItemTaskSignature):
            # Include the original task as a child
            original_node = await build_node(task.original_task_id, depth + 1)
            if original_node:
                children = [original_node]

        # Get callbacks if requested
        if include_callbacks:
            if task.success_callbacks:
                cb_nodes = await asyncio.gather(
                    *[
                        build_node(cb_id, depth + 1)
                        for cb_id in task.success_callbacks
                    ],
                    return_exceptions=True,
                )
                success_cb_nodes = [c for c in cb_nodes if isinstance(c, TaskGraphNode)]

            if task.error_callbacks:
                cb_nodes = await asyncio.gather(
                    *[build_node(cb_id, depth + 1) for cb_id in task.error_callbacks],
                    return_exceptions=True,
                )
                error_cb_nodes = [c for c in cb_nodes if isinstance(c, TaskGraphNode)]

        return TaskGraphNode(
            task_id=task.key,
            task_type=_get_task_type(task),
            task_name=task.task_name,
            status=task.task_status.status.value,
            children=children,
            success_callbacks=success_cb_nodes,
            error_callbacks=error_cb_nodes,
        )

    return await build_node(task_id, 0)


async def get_chain_tasks(
    chain_id: str,
    offset: int = 0,
    limit: int = 20,
) -> Optional[ChainTasksResponse]:
    """
    Get subtasks of a chain with pagination.

    Args:
        chain_id: The chain task identifier
        offset: Starting position (0-indexed)
        limit: Maximum number of tasks to return

    Returns:
        ChainTasksResponse with paginated task list, or None if not found
    """
    task = await TaskSignature.get_safe(chain_id)
    if task is None or not isinstance(task, ChainTaskSignature):
        return None

    total_tasks = len(task.tasks)
    task_ids = list(task.tasks)[offset : offset + limit]

    tasks_data = await asyncio.gather(
        *[TaskSignature.get_safe(tid) for tid in task_ids],
        return_exceptions=True,
    )

    tasks = []
    for i, t in enumerate(tasks_data):
        if isinstance(t, TaskSignature):
            kwargs = {}
            try:
                kwargs = dict(t.kwargs) if t.kwargs else {}
            except Exception:
                pass
            tasks.append(
                ChainTaskInfo(
                    task_id=t.key,
                    task_name=t.task_name,
                    status=t.task_status.status.value,
                    position=offset + i,
                    kwargs=kwargs,
                )
            )

    return ChainTasksResponse(
        chain_id=chain_id,
        chain_name=task.task_name,
        total_tasks=total_tasks,
        offset=offset,
        limit=limit,
        tasks=tasks,
        has_more=(offset + limit) < total_tasks,
    )


async def get_chain_status(chain_id: str) -> Optional[ChainStatusResponse]:
    """
    Get chain execution status summary.

    Args:
        chain_id: The chain task identifier

    Returns:
        ChainStatusResponse with status summary, or None if not found
    """
    task = await TaskSignature.get_safe(chain_id)
    if task is None or not isinstance(task, ChainTaskSignature):
        return None

    total_tasks = len(task.tasks)

    # Find the current task (first non-completed task)
    current_task_index = 0
    current_task_id = None
    current_task_name = None
    current_task_status = None
    completed_tasks = 0
    pending_tasks = 0

    if task.tasks:
        subtasks = await asyncio.gather(
            *[TaskSignature.get_safe(tid) for tid in task.tasks],
            return_exceptions=True,
        )

        for i, subtask in enumerate(subtasks):
            if not isinstance(subtask, TaskSignature):
                continue

            status = subtask.task_status.status
            if status == SignatureStatus.PENDING:
                pending_tasks += 1
                if current_task_id is None:
                    current_task_index = i
                    current_task_id = subtask.key
                    current_task_name = subtask.task_name
                    current_task_status = status.value
            elif status == SignatureStatus.ACTIVE:
                current_task_index = i
                current_task_id = subtask.key
                current_task_name = subtask.task_name
                current_task_status = status.value
            elif status in [SignatureStatus.SUSPENDED, SignatureStatus.INTERRUPTED]:
                if current_task_id is None:
                    current_task_index = i
                    current_task_id = subtask.key
                    current_task_name = subtask.task_name
                    current_task_status = status.value
            else:
                # Completed or canceled
                completed_tasks += 1

    return ChainStatusResponse(
        chain_id=chain_id,
        chain_name=task.task_name,
        status=task.task_status.status.value,
        total_tasks=total_tasks,
        current_task_index=current_task_index,
        current_task_id=current_task_id,
        current_task_name=current_task_name,
        current_task_status=current_task_status,
        completed_tasks=completed_tasks,
        pending_tasks=pending_tasks,
    )


async def get_swarm_tasks(
    swarm_id: str,
    offset: int = 0,
    limit: int = 20,
    filter_status: Optional[str] = None,
) -> Optional[SwarmTasksResponse]:
    """
    Get subtasks of a swarm with pagination.

    Args:
        swarm_id: The swarm task identifier
        offset: Starting position (0-indexed)
        limit: Maximum number of tasks to return
        filter_status: Optional status filter ("pending", "active", "completed", "failed")

    Returns:
        SwarmTasksResponse with paginated task list, or None if not found
    """
    task = await TaskSignature.get_safe(swarm_id)
    if task is None or not isinstance(task, SwarmTaskSignature):
        return None

    # Determine which task list to use based on filter
    if filter_status == "completed":
        task_ids = list(task.finished_tasks)
    elif filter_status == "failed":
        task_ids = list(task.failed_tasks)
    elif filter_status == "pending":
        task_ids = list(task.tasks_left_to_run)
    else:
        task_ids = list(task.tasks)

    total_tasks = len(task_ids)
    paginated_ids = task_ids[offset : offset + limit]

    tasks_data = await asyncio.gather(
        *[TaskSignature.get_safe(tid) for tid in paginated_ids],
        return_exceptions=True,
    )

    tasks = []
    for t in tasks_data:
        if isinstance(t, BatchItemTaskSignature):
            kwargs = {}
            try:
                kwargs = dict(t.kwargs) if t.kwargs else {}
            except Exception:
                pass
            tasks.append(
                SwarmTaskInfo(
                    task_id=t.key,
                    task_name=t.task_name,
                    original_task_id=t.original_task_id,
                    status=t.task_status.status.value,
                    kwargs=kwargs,
                )
            )
        elif isinstance(t, TaskSignature):
            kwargs = {}
            try:
                kwargs = dict(t.kwargs) if t.kwargs else {}
            except Exception:
                pass
            tasks.append(
                SwarmTaskInfo(
                    task_id=t.key,
                    task_name=t.task_name,
                    original_task_id="",
                    status=t.task_status.status.value,
                    kwargs=kwargs,
                )
            )

    return SwarmTasksResponse(
        swarm_id=swarm_id,
        swarm_name=task.task_name,
        total_tasks=total_tasks,
        offset=offset,
        limit=limit,
        tasks=tasks,
        has_more=(offset + limit) < total_tasks,
    )


async def get_swarm_status(swarm_id: str) -> Optional[SwarmStatusResponse]:
    """
    Get swarm execution status summary.

    Args:
        swarm_id: The swarm task identifier

    Returns:
        SwarmStatusResponse with status summary, or None if not found
    """
    task = await TaskSignature.get_safe(swarm_id)
    if task is None or not isinstance(task, SwarmTaskSignature):
        return None

    total_tasks = len(task.tasks)
    completed_tasks = len(task.finished_tasks)
    failed_tasks = len(task.failed_tasks)
    tasks_left_to_run = len(task.tasks_left_to_run)
    running_tasks = int(task.current_running_tasks)

    # Pending = total - completed - failed - running
    pending_tasks = total_tasks - completed_tasks - failed_tasks - running_tasks
    if pending_tasks < 0:
        pending_tasks = 0

    results_count = 0
    try:
        results_count = len(task.tasks_results)
    except Exception:
        pass

    return SwarmStatusResponse(
        swarm_id=swarm_id,
        swarm_name=task.task_name,
        status=task.task_status.status.value,
        is_closed=task.is_swarm_closed,
        total_tasks=total_tasks,
        running_tasks=running_tasks,
        completed_tasks=completed_tasks,
        failed_tasks=failed_tasks,
        pending_tasks=pending_tasks,
        tasks_left_to_run=tasks_left_to_run,
        max_concurrency=task.config.max_concurrency,
        stop_after_n_failures=task.config.stop_after_n_failures,
        max_task_allowed=task.config.max_task_allowed,
        results_count=results_count,
    )
