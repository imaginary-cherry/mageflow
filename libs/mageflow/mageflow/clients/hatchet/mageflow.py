import asyncio
import functools
import inspect
import random
from datetime import timedelta
from typing import Any, Unpack, Callable, TypedDict

from hatchet_sdk import Hatchet, Worker, Context
from hatchet_sdk.labels import DesiredWorkerLabel
from hatchet_sdk.rate_limit import RateLimit
from hatchet_sdk.runnables.types import (
    StickyStrategy,
    ConcurrencyExpression,
    DefaultFilter,
)
from hatchet_sdk.runnables.workflow import BaseWorkflow, Standalone
from hatchet_sdk.worker.worker import LifespanFn
from redis.asyncio import Redis
from thirdmagic import sign, chain
from thirdmagic.signature import Signature
from thirdmagic.swarm.creator import SignatureOptions, swarm
from thirdmagic.task import TaskSignatureConvertible, TaskSignature, TaskInputType
from thirdmagic.task_def import MageflowTaskDefinition
from thirdmagic.utils import HatchetTaskType
from typing_extensions import override

from mageflow.callbacks import AcceptParams, handle_task_callback
from mageflow.init import init_mageflow_hatchet_tasks
from mageflow.startup import (
    lifespan_initialize,
    init_mageflow,
    teardown_mageflow,
)
from mageflow.utils.mageflow import does_task_wants_ctx

Duration = timedelta | str


class TaskOptions(TypedDict, total=False):
    name: str | None
    description: str | None
    input_validator: type | None
    on_events: list[str] | None
    on_crons: list[str] | None
    version: str | None
    sticky: StickyStrategy | None
    default_priority: int
    concurrency: int | ConcurrencyExpression | list[ConcurrencyExpression] | None
    schedule_timeout: Duration
    execution_timeout: Duration
    retries: int
    rate_limits: list[RateLimit] | None
    desired_worker_labels: dict[str, DesiredWorkerLabel] | None
    backoff_factor: float | None
    backoff_max_seconds: int | None
    default_filters: list[DefaultFilter] | None
    default_additional_metadata: dict[str, Any] | None


class WorkerOptions(TypedDict, total=False):
    slots: int
    durable_slots: int
    labels: dict[str, str | int] | None


async def merge_lifespan(
    redis: Redis, tasks: list[MageflowTaskDefinition], original_lifespan: LifespanFn
):
    await init_mageflow(redis, tasks)
    async for res in original_lifespan():
        yield res
    await teardown_mageflow()


class HatchetMageflow(Hatchet):
    def __init__(
        self,
        hatchet: Hatchet,
        redis_client: Redis,
        param_config: AcceptParams = AcceptParams.NO_CTX,
    ):
        super().__init__(client=hatchet._client)
        self.hatchet = hatchet
        self.redis = redis_client
        self.param_config = param_config
        self._task_defs: list[MageflowTaskDefinition] = []

    def _add_task_def(self, task: Standalone):
        self._task_defs.append(
            MageflowTaskDefinition(
                mageflow_task_name=task.name,
                task_name=task.name,
                retries=Signature.ClientAdapter.extract_retries(task),
                input_validator=Signature.ClientAdapter.extract_validator(task),
            )
        )

    def task_decorator(self, func: Callable, name: str, hatchet_task):
        param_config = (
            AcceptParams.ALL if does_task_wants_ctx(func) else self.param_config
        )
        send_signature = getattr(func, "__send_signature__", False)
        handler_dec = handle_task_callback(param_config, send_signature=send_signature)
        func = handler_dec(func)
        wf = hatchet_task(func)
        self._add_task_def(wf)

        return wf

    @override
    def task(self, *, name: str | None = None, **kwargs: Unpack[TaskOptions]):
        """
        This is a wrapper for task, if you want to see hatchet task go to parent class
        """
        hatchet_task = super().task(name=name, **kwargs)

        decorator = functools.partial(
            self.task_decorator, name=name, hatchet_task=hatchet_task
        )
        return decorator

    @override
    def durable_task(self, *, name: str | None = None, **kwargs: Unpack[TaskOptions]):
        """
        This is a wrapper for durable task, if you want to see hatchet durable task go to parent class
        """
        hatchet_task = super().durable_task(name=name, **kwargs)

        decorator = functools.partial(
            self.task_decorator, name=name, hatchet_task=hatchet_task
        )

        return decorator

    @override
    def worker(
        self,
        name: str,
        workflows: list[BaseWorkflow[Any]] | None = None,
        lifespan: LifespanFn | None = None,
        **kwargs: Unpack[WorkerOptions],
    ) -> Worker:
        mageflow_flows = init_mageflow_hatchet_tasks(self.hatchet)
        workflows += mageflow_flows
        if lifespan is None:
            lifespan = functools.partial(
                lifespan_initialize, self.redis, self._task_defs
            )
        else:
            lifespan = functools.partial(
                merge_lifespan, self.redis, self._task_defs, lifespan
            )

        return super().worker(name, workflows=workflows, lifespan=lifespan, **kwargs)

    async def asign(self, task: str | HatchetTaskType, **options: Any) -> TaskSignature:
        return await sign(task, **options)

    async def achain(
        self,
        tasks: list[TaskSignatureConvertible],
        name: str = None,
        error: TaskInputType = None,
        success: TaskInputType = None,
    ):
        return await chain(tasks, name, error, success)

    async def aswarm(
        self,
        tasks: list[TaskSignatureConvertible] = None,
        task_name: str = None,
        **kwargs: Unpack[SignatureOptions],
    ):
        return await swarm(tasks, task_name, **kwargs)

    def with_ctx(self, func):
        func.__user_ctx__ = True
        return func

    def with_signature(self, func):
        func.__send_signature__ = True
        return func

    def stagger_execution(self, wait_delta: timedelta):
        def decorator(func):
            @self.with_ctx
            @functools.wraps(func)
            async def stagger_wrapper(message, ctx: Context, *args, **kwargs):
                stagger = random.uniform(0, wait_delta.total_seconds())
                ctx.log(f"Staggering for {stagger:.2f} seconds")
                ctx.refresh_timeout(timedelta(seconds=stagger))
                await asyncio.sleep(stagger)

                if does_task_wants_ctx(func):
                    return await func(message, ctx, *args, **kwargs)
                else:
                    return await func(message, *args, **kwargs)

            stagger_wrapper.__signature__ = inspect.signature(func)
            return stagger_wrapper

        return decorator
