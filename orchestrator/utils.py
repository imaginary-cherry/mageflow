import base64
from typing import Optional

import cloudpickle
from pydantic import BaseModel


def parse_model_validator(
    validator: type[BaseModel] | bytes,
) -> Optional[type[BaseModel]]:
    if isinstance(validator, str):
        validator = base64.b64decode(validator.encode("ascii"))
    if isinstance(validator, bytes):
        return cloudpickle.loads(validator)
    elif isinstance(validator, type) and issubclass(validator, BaseModel):
        return validator
    return None


def serialize_model_validator(validator: Optional[type[BaseModel]]) -> Optional[str]:
    if validator is None:
        return None
    pkl = cloudpickle.dumps(validator)
    return base64.b64encode(pkl).decode("ascii")


class FakeModel(BaseModel):
    pass
