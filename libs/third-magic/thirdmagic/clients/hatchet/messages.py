from typing import Any, Optional

from pydantic import BaseModel

## Chain


class ChainMessage(BaseModel):
    chain_task_id: str


class ChainCallbackMessage(ChainMessage):
    chain_results: Any


class ChainErrorMessage(ChainMessage):
    error: str
    original_msg: dict
    error_task_key: str


## Swarm


class SwarmMessage(BaseModel):
    swarm_task_id: str


class SwarmCallbackMessage(SwarmMessage):
    swarm_item_id: str


class SwarmResultsMessage(SwarmCallbackMessage):
    mageflow_results: Any


class SwarmErrorMessage(SwarmCallbackMessage):
    error: Optional[str] = None
