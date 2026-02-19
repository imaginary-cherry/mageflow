from typing import Any, Optional

from pydantic import BaseModel
from rapyer.fields import RapyerKey


class SwarmMessage(BaseModel):
    swarm_task_id: RapyerKey


class SwarmCallbackMessage(SwarmMessage):
    swarm_item_id: RapyerKey


class SwarmResultsMessage(SwarmCallbackMessage):
    mageflow_results: Any


class SwarmErrorMessage(SwarmCallbackMessage):
    error: str


class FillSwarmMessage(SwarmMessage):
    max_tasks: Optional[int] = None
