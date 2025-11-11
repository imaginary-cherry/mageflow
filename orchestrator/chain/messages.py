from typing import Any, Annotated

from pydantic import BaseModel

from orchestrator.models.message import ReturnValue


class ChainSuccessTaskCommandMessage(BaseModel):
    chain_results: Annotated[Any, ReturnValue()]
