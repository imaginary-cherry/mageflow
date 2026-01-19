from pydantic import BaseModel

from mageflow.signature.model import TaskSignature


class TaskCallbacksResponse(BaseModel):
    success_callbacks: list[TaskSignature]
    error_callbacks: list[TaskSignature]


class TaskChildrenResponse(BaseModel):
    children: list[TaskSignature]
