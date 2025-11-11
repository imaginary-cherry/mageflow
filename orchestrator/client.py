from datetime import timedelta
from typing import TypeVar, Callable, Concatenate

from hatchet_sdk import Hatchet, DurableContext
from hatchet_sdk.hatchet import P
from hatchet_sdk.labels import DesiredWorkerLabel
from hatchet_sdk.rate_limit import RateLimit
from hatchet_sdk.runnables.types import (
    TWorkflowInput,
    StickyStrategy,
    ConcurrencyExpression,
    DefaultFilter,
    EmptyModel,
    R,
)
from hatchet_sdk.runnables.workflow import Standalone
from hatchet_sdk.utils.timedelta_to_expression import Duration
from hatchet_sdk.utils.typing import CoroutineLike

from orchestrator.callbacks import AcceptParams, register_task, handle_task_callback


class HatchetOrchestrator(Hatchet):
    # To support the __getattribute__func
    hatchet = None
    param_config = None

    def __init__(
        self, hatchet: Hatchet, param_config: AcceptParams = AcceptParams.NO_CTX
    ):
        super().__init__(client=hatchet._client)
        self.hatchet = hatchet
        self.param_config = param_config

    def __getattribute__(self, item):
        cls = object.__getattribute__(self, "__class__")
        if item in cls.__dict__:
            return object.__getattribute__(self, item)
        else:
            hatchet = object.__getattribute__(self, "hatchet")
            return getattr(hatchet, item)

    def task(self, *, name: str | None = None, **kwargs):
        hatchet_task = super().task(name=name, **kwargs)

        def decorator(func):
            handler_dec = handle_task_callback(self.param_config)
            func = handler_dec(func)
            wf = hatchet_task(func)
            register = register_task(name)
            return register(wf)

        return decorator

    def durable_task(self, *, name: str | None = None, **kwargs):
        hatchet_task = super().durable_task(name=name, **kwargs)

        def decorator(func):
            handler_dec = handle_task_callback(self.param_config)
            func = handler_dec(func)
            wf = hatchet_task(func)
            register = register_task(name)
            return register(wf)

        return decorator


T = TypeVar("T")


def Orchestrator(
    hatchet_client: T = None, param_config: AcceptParams = AcceptParams.NO_CTX
) -> T:
    return HatchetOrchestrator(hatchet_client, param_config)
