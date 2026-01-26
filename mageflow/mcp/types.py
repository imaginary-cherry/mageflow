"""Type definitions for MCP tool responses."""

from typing import Any, Optional
from pydantic import BaseModel


class TaskInfo(BaseModel):
    """Basic task information."""

    task_id: str
    task_type: str
    task_name: str
    status: str
    last_status: str
    worker_task_id: str
    creation_time: Optional[str] = None
    kwargs: dict[str, Any] = {}
    task_identifiers: dict[str, Any] = {}
    success_callbacks_count: int = 0
    error_callbacks_count: int = 0


class CallbackInfo(BaseModel):
    """Callback task information."""

    task_id: str
    task_name: str
    status: str
    kwargs: dict[str, Any] = {}


class CallbacksResponse(BaseModel):
    """Response for get_task_callbacks."""

    task_id: str
    success_callbacks: list[CallbackInfo] = []
    error_callbacks: list[CallbackInfo] = []


class ChainTaskInfo(BaseModel):
    """Chain subtask information."""

    task_id: str
    task_name: str
    status: str
    position: int
    kwargs: dict[str, Any] = {}


class ChainTasksResponse(BaseModel):
    """Response for get_chain_tasks with pagination."""

    chain_id: str
    chain_name: str
    total_tasks: int
    offset: int
    limit: int
    tasks: list[ChainTaskInfo] = []
    has_more: bool = False


class ChainStatusResponse(BaseModel):
    """Response for get_chain_status."""

    chain_id: str
    chain_name: str
    status: str
    total_tasks: int
    current_task_index: int
    current_task_id: Optional[str] = None
    current_task_name: Optional[str] = None
    current_task_status: Optional[str] = None
    completed_tasks: int = 0
    pending_tasks: int = 0


class SwarmTaskInfo(BaseModel):
    """Swarm subtask information."""

    task_id: str
    task_name: str
    original_task_id: str
    status: str
    kwargs: dict[str, Any] = {}


class SwarmTasksResponse(BaseModel):
    """Response for get_swarm_tasks with pagination."""

    swarm_id: str
    swarm_name: str
    total_tasks: int
    offset: int
    limit: int
    tasks: list[SwarmTaskInfo] = []
    has_more: bool = False


class SwarmStatusResponse(BaseModel):
    """Response for get_swarm_status."""

    swarm_id: str
    swarm_name: str
    status: str
    is_closed: bool
    total_tasks: int
    running_tasks: int
    completed_tasks: int
    failed_tasks: int
    pending_tasks: int
    tasks_left_to_run: int
    max_concurrency: int
    stop_after_n_failures: Optional[int] = None
    max_task_allowed: Optional[int] = None
    results_count: int = 0


class TaskGraphNode(BaseModel):
    """Node in task graph."""

    task_id: str
    task_type: str
    task_name: str
    status: str
    children: list["TaskGraphNode"] = []
    success_callbacks: list["TaskGraphNode"] = []
    error_callbacks: list["TaskGraphNode"] = []


TaskGraphNode.model_rebuild()
