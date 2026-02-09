from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from mageflow.chain.model import ChainTaskSignature
from mageflow.signature.model import TaskSignature
from mageflow.signature.status import SignatureStatus

TaskStatus = Literal[
    "pending", "running", "paused", "cancelled", "completed", "failed"
]

STATUS_MAPPING: dict[SignatureStatus, TaskStatus] = {
    SignatureStatus.PENDING: "pending",
    SignatureStatus.ACTIVE: "running",
    SignatureStatus.FAILED: "failed",
    SignatureStatus.DONE: "completed",
    SignatureStatus.SUSPENDED: "paused",
    SignatureStatus.INTERRUPTED: "paused",
    SignatureStatus.CANCELED: "cancelled",
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
    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: str
    name: str
    status: TaskStatus
    subtask_ids: list[str] = Field(serialization_alias="children_ids")
    success_callback_ids: list[str]
    error_callback_ids: list[str]
    kwargs: dict[str, Any] = Field(serialization_alias="metadata")
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


def serialize_task(task: TaskSignature) -> TaskFromServer:
    return TaskFromServer(
        id=task.key,
        type=task.__class__.__name__,
        name=task.task_name,
        status=STATUS_MAPPING.get(task.task_status.status, "pending"),
        subtask_ids=task.task_ids if isinstance(task, ChainTaskSignature) else [],
        success_callback_ids=list(task.success_callbacks),
        error_callback_ids=list(task.error_callbacks),
        kwargs=dict(task.kwargs),
        created_at=task.creation_time.isoformat(),
    )
