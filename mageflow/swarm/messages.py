from typing import Any, Optional

from pydantic import BaseModel


class SwarmMessage(BaseModel):
    swarm_task_id: str


class SwarmCallbackMessage(SwarmMessage):
    swarm_item_id: str


class SwarmResultsMessage(SwarmCallbackMessage):
    mageflow_results: Any


class SwarmErrorMessage(SwarmCallbackMessage):
    error: Optional[str] = None
