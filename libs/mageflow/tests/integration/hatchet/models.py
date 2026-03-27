from typing import Any

from pydantic import BaseModel, Field
from thirdmagic.message import ReturnValue


class BaseWorkerMessage(BaseModel):
    test_ctx: dict = Field(default_factory=dict)


class ContextMessage(BaseWorkerMessage):
    base_data: dict = Field(default_factory=dict)
    more_context: dict = Field(default_factory=dict)


class MessageWithMsgResults(ContextMessage):
    msg_results: ReturnValue[ContextMessage]


class MessageWithData(ContextMessage):
    data: ReturnValue[Any]
    field_int: int = 1
    field_str: str = "test"
    field_list: list[int]


class MessageWithResult(BaseModel):
    mageflow_results: Any


class ErrorMessage(ContextMessage):
    error: str


class CommandMessageWithResult(ContextMessage):
    task_result: ReturnValue[Any]


class SleepTaskMessage(ContextMessage):
    sleep_time: int = 2
    result: Any = None


class SignatureKeysResult(BaseModel):
    task_keys: list[str]
    chain_key: str
    chain_sub_task_keys: list[str]
    swarm_key: str
    swarm_sub_task_keys: list[str]
    publish_state_key: str

    def is_key_in_keys(self, key: str) -> bool:
        if key in self.task_keys:
            return True
        if key in self.chain_sub_task_keys:
            return True
        if key in self.swarm_sub_task_keys:
            return True
        if key == self.publish_state_key:
            return True
        if key == self.chain_key:
            return True
        if key == self.swarm_key:
            return True
        return False


class SignatureKeyWithWF(SignatureKeysResult):
    workflow_run_id: str


class CacheIsolationMessage(ContextMessage):
    sig_count: int = 1


class MageflowTestError(Exception):
    pass
