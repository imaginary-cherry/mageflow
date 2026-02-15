from typing import Any

from pydantic import BaseModel


class ChainMessage(BaseModel):
    chain_task_id: str


class ChainCallbackMessage(ChainMessage):
    chain_results: Any


class ChainErrorMessage(ChainMessage):
    error: str
    original_msg: dict
    error_task_key: str
