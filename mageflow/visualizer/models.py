from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from mageflow.chain.model import ChainTaskSignature
from mageflow.signature.model import TaskSignature
from mageflow.signature.status import SignatureStatus
from mageflow.swarm.model import BatchItemTaskSignature, SwarmTaskSignature

TaskType = Literal["task", "chain", "swarm", "batch_item"]
TaskStatus = Literal[
    "pending", "active", "suspended", "interrupted", "canceled", "completed", "failed"
]

STATUS_MAPPING: dict[SignatureStatus, TaskStatus] = {
    SignatureStatus.PENDING: "pending",
    SignatureStatus.ACTIVE: "active",
    SignatureStatus.FAILED: "failed",
    SignatureStatus.DONE: "completed",
    SignatureStatus.SUSPENDED: "suspended",
    SignatureStatus.INTERRUPTED: "interrupted",
    SignatureStatus.CANCELED: "canceled",
}


def to_camel(string: str) -> str:
    components = string.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


class CamelCaseModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class TaskFromServer(BaseModel):
    id: str
    type: TaskType
    name: str
    status: TaskStatus
    parent_id: str | None
    subtask_ids: list[str]
    success_callback_ids: list[str]
    error_callback_ids: list[str]
    kwargs: dict[str, Any]
    created_at: str


class TaskCallbacksResponse(BaseModel):
    success_callback_ids: list[str]
    error_callback_ids: list[str]


class TaskChildrenResponse(CamelCaseModel):
    task_ids: list[str]
    total_count: int
    page: int
    page_size: int


class RootTasksResponse(CamelCaseModel):
    task_ids: list[str]


class BatchTasksRequest(CamelCaseModel):
    task_ids: list[str]


def get_task_type(task: TaskSignature) -> TaskType:
    if isinstance(task, ChainTaskSignature):
        return "chain"
    elif isinstance(task, SwarmTaskSignature):
        return "swarm"
    elif isinstance(task, BatchItemTaskSignature):
        return "batch_item"
    return "task"


def get_subtask_ids(task: TaskSignature) -> list[str]:
    if isinstance(task, ChainTaskSignature):
        return list(task.tasks)
    elif isinstance(task, SwarmTaskSignature):
        return list(task.tasks)
    return []


def get_parent_id(task: TaskSignature) -> str | None:
    if isinstance(task, BatchItemTaskSignature):
        return task.swarm_id
    return None


def serialize_task(task: TaskSignature) -> TaskFromServer:
    return TaskFromServer(
        id=task.key,
        type=get_task_type(task),
        name=task.task_name,
        status=STATUS_MAPPING.get(task.task_status.status, "pending"),
        parent_id=get_parent_id(task),
        subtask_ids=get_subtask_ids(task),
        success_callback_ids=list(task.success_callbacks),
        error_callback_ids=list(task.error_callbacks),
        kwargs=dict(task.kwargs),
        created_at=task.creation_time.isoformat() if task.creation_time else "",
    )
