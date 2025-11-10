from typing import Optional, Annotated

from pydantic import BaseModel
from rapyer import AtomicRedisModel
from rapyer.fields import Key


class HatchetTaskModel(AtomicRedisModel):
    task_name: Annotated[str, Key()]
    input_validator: Optional[type[BaseModel]] = None
