from typing import Any

from pydantic import BaseModel

from mageflow.models.message import ReturnValue


class ChainCallbackMessage(BaseModel):
    chain_results: ReturnValue[Any]
    chain_task_id: str
