from typing import Any

from pydantic import BaseModel, Field

from thirdmagic.message import ReturnValue


class BaseWorkerMessage(BaseModel):
    test_ctx: dict = Field(default_factory=dict)


class ContextMessage(BaseWorkerMessage):
    base_data: dict = Field(default_factory=dict)


class MessageWithData(ContextMessage):
    data: ReturnValue[Any]
    field_int: int = 1
    field_str: str = "test"
    field_list: list[int]


class CommandMessageWithResult(ContextMessage):
    task_result: ReturnValue[Any]
