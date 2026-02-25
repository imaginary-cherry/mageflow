from typing import Optional

from pydantic import BaseModel
from rapyer import AtomicRedisModel
from rapyer.fields import Key


class MageflowTaskDefinition(AtomicRedisModel):
    mageflow_task_name: Key[str]
    task_name: str
    input_validator: Optional[type[BaseModel]] = None
    retries: Optional[int] = None
