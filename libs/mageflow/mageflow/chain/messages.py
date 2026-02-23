from typing import Any

from pydantic import BaseModel
from rapyer.fields import RapyerKey


class ChainMessage(BaseModel):
    chain_task_id: RapyerKey


class ChainCallbackMessage(ChainMessage):
    chain_results: Any


class ChainErrorMessage(ChainMessage):
    error: str
    original_msg: dict
    error_task_key: RapyerKey
