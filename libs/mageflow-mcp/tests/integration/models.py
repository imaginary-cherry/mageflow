from typing import Any

from pydantic import BaseModel, Field

from thirdmagic.message import ReturnValue


class ContextMessage(BaseModel):
    base_data: dict = Field(default_factory=dict)


class CommandMessageWithResult(ContextMessage):
    task_result: ReturnValue[Any]


class MageflowTestError(Exception):
    pass
