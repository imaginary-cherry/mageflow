from typing import Generic, TypeVar, Any
from pydantic_core import core_schema

DEFAULT_RESULT_NAME = "mageflow_results"
T = TypeVar("T")


class ReturnValue(Generic[T]):
    def __init__(self, value: T):
        self.value = value

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        inner_type = source_type.__args__[0]
        inner_schema = handler(inner_type)

        def validate(value: Any, info: core_schema.ValidationInfo):
            if value is not None:
                return value

            if info.data is not None:
                if DEFAULT_RESULT_NAME in info.data:
                    return info.data[DEFAULT_RESULT_NAME]

            return value

        return core_schema.with_info_after_validator_function(
            validate,
            inner_schema,
        )
