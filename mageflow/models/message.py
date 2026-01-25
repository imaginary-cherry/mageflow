import dataclasses
from typing import Generic, TypeVar, Any, Annotated, TYPE_CHECKING, TypeAlias

DEFAULT_RESULT_NAME = "mageflow_results"
T = TypeVar("T")


@dataclasses.dataclass(frozen=True)
class ReturnValueAnnotation:
    pass


class _ReturnValue(Generic[T]):
    def __new__(cls, typ: Any = None):
        if typ is None:
            return ReturnValueAnnotation()
        return Annotated[typ, ReturnValueAnnotation()]

    def __class_getitem__(cls, item):
        return Annotated[item, ReturnValueAnnotation()]


ReturnValue = _ReturnValue

if TYPE_CHECKING:
    ReturnValue: TypeAlias = Annotated[T, ReturnValueAnnotation()]
