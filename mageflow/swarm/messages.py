from typing import Any

from pydantic import BaseModel


class SwarmMessage(BaseModel):
    swarm_task_id: str


class SwarmCallbackMessage(SwarmMessage):
    swarm_item_id: str
    swarm_task_id: str


class SwarmResultsMessage(SwarmCallbackMessage):
    results: Any
