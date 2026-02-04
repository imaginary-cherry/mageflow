from typing import Any

from pydantic import BaseModel

from mageflow.models.message import ReturnValue


class ChainMessage(BaseModel):
    chain_task_id: str


class ChainCallbackMessage(ChainMessage):
    chain_results: ReturnValue[Any]
    chain_task_id: str


class ChainErrorMessage(ChainMessage):
    error: str
    original_msg: dict
    error_task_key: str
