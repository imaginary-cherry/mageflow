from typing import Any

from pydantic import BaseModel

from mageflow.models.message import ReturnValue


class ChainSuccessTaskCommandMessage(BaseModel):
    chain_results: ReturnValue[Any]
