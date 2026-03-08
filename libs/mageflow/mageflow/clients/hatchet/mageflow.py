import asyncio
import functools
import inspect
import random
from datetime import timedelta
from typing import Any, Callable, TypedDict, Unpack

from hatchet_sdk import Context, Hatchet, Worker
from hatchet_sdk.labels import DesiredWorkerLabel
from hatchet_sdk.rate_limit import RateLimit
from hatchet_sdk.runnables.types import (
    ConcurrencyExpression,
    ConcurrencyLimitStrategy,
    DefaultFilter,
    StickyStrategy,
)
from hatchet_sdk.runnables.workflow import BaseWorkflow, Standalone
from hatchet_sdk.worker.worker import LifespanFn
from redis.asyncio import Redis
from typing_extensions import override

from mageflow.callbacks import AcceptParams, handle_task_callback
from mageflow.chain.messages import ChainCallbackMessage, ChainErrorMessage
from mageflow.chain.workflows import chain_end_task, chain_error_task
from mageflow.clients.inner_task_names import (
    ON_CHAIN_END,
    ON_CHAIN_ERROR,
    ON_SWARM_ITEM_DONE,
    ON_SWARM_ITEM_ERROR,
    SWARM_FILL_TASK,
)
from mageflow.config import MageflowConfig
from mageflow.startup import (
    init_mageflow,
    lifespan_initialize,
    teardown_mageflow,
)
from mageflow.swarm.consts import SWARM_TASK_ID_PARAM_NAME
from mageflow.swarm.messages import (
    FillSwarmMessage,
    SwarmErrorMessage,
    SwarmResultsMessage,
)
from mageflow.swarm.workflows import (
    fill_swarm_running_tasks,
    swarm_item_done,
    swarm_item_failed,
)
from mageflow.utils.mageflow import does_task_wants_ctx
from thirdmagic import chain, sign
from thirdmagic.chain import ChainTaskSignature
from thirdmagic.signature import Signature
from thirdmagic.swarm import SwarmTaskSignature
from thirdmagic.swarm.creator import SignatureOptions, swarm
from thirdmagic.task import TaskInputType, TaskSignature, TaskSignatureConvertible
from thirdmagic.task_def import MageflowTaskDefinition
from thirdmagic.utils import HatchetTaskType

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
    redis: Redis,
    tasks: list[MageflowTaskDefinition],
    config: MageflowConfig,
    original_lifespan: LifespanFn,
):
    await init_mageflow(redis, tasks, config)
    async for res in original_lifespan():
        yield res
    await teardown_mageflow()


class HatchetMageflow(Hatchet):
    def __init__(
        self,
        hatchet: Hatchet,
        redis_client: Redis,
        config: MageflowConfig = None,
    ):
        super().__init__(client=hatchet._client)
        self.hatchet = hatchet
        self.redis = redis_client
        self.mageflow_config = config or MageflowConfig()
        self._task_defs: list[MageflowTaskDefinition] = []

    @property
    def mageflow_logger(self):
        return self.config.logger

    def _add_task_def(self, task: Standalone):
        self._task_defs.append(
            MageflowTaskDefinition(
                mageflow_task_name=task.name,
                task_name=task.name,
                retries=Signature.ClientAdapter.extract_retries(task),
                input_validator=Signature.ClientAdapter.extract_validator(task),
            )
        )

    def task_decorator(self, func: Callable, hatchet_task, durable: bool = False):
        param_config = (
            AcceptParams.ALL
            if does_task_wants_ctx(func)
            else self.mageflow_config.param_config
        )
        send_signature = getattr(func, "__send_signature__", False)
        handler_dec = handle_task_callback(
            param_config, send_signature=send_signature, durable=durable
        )
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
            self.task_decorator, hatchet_task=hatchet_task, durable=False
        )
        return decorator

    @override
    def durable_task(self, *, name: str | None = None, **kwargs: Unpack[TaskOptions]):
        """
        This is a wrapper for durable task, if you want to see hatchet durable task go to parent class
        """
        hatchet_task = super().durable_task(name=name, **kwargs)

        decorator = functools.partial(
            self.task_decorator, hatchet_task=hatchet_task, durable=True
        )

        return decorator

    def init_mageflow_hatchet_tasks(self):
        # Chain tasks
        hatchet_chain_done = self.hatchet.durable_task(
            name=ON_CHAIN_END,
            input_validator=ChainCallbackMessage,
            retries=3,
            execution_timeout=timedelta(minutes=5),
        )
        hatchet_chain_error = self.hatchet.durable_task(
            name=ON_CHAIN_ERROR,
            input_validator=ChainErrorMessage,
            retries=3,
            execution_timeout=timedelta(minutes=5),
        )
        chain_done_task = hatchet_chain_done(self.chain_end_task)
        on_chain_error_task = hatchet_chain_error(self.chain_error_task)

        # Swarm tasks
        swarm_done = self.hatchet.durable_task(
            name=ON_SWARM_ITEM_DONE,
            input_validator=SwarmResultsMessage,
            retries=5,
            execution_timeout=timedelta(minutes=1),
        )
        swarm_error = self.hatchet.durable_task(
            name=ON_SWARM_ITEM_ERROR,
            input_validator=SwarmErrorMessage,
            retries=5,
            execution_timeout=timedelta(minutes=5),
        )
        swarm_done = swarm_done(self.swarm_item_done)
        swarm_error = swarm_error(self.swarm_item_failed)

        swarm_fill_task = self.hatchet.durable_task(
            name=SWARM_FILL_TASK,
            input_validator=FillSwarmMessage,
            execution_timeout=timedelta(minutes=5),
            retries=4,
            concurrency=[
                ConcurrencyExpression(
                    expression=f"input.{SWARM_TASK_ID_PARAM_NAME}",
                    max_runs=2,
                    limit_strategy=ConcurrencyLimitStrategy.CANCEL_NEWEST,
                ),
                ConcurrencyExpression(
                    expression=f"input.{SWARM_TASK_ID_PARAM_NAME}",
                    max_runs=1,
                    limit_strategy=ConcurrencyLimitStrategy.GROUP_ROUND_ROBIN,
                ),
            ],
        )
        swarm_fill_task = swarm_fill_task(self.fill_swarm_running_tasks)

        return [
            chain_done_task,
            on_chain_error_task,
            swarm_done,
            swarm_error,
            swarm_fill_task,
        ]

    @override
    def worker(
        self,
        name: str,
        workflows: list[BaseWorkflow[Any]] | None = None,
        lifespan: LifespanFn | None = None,
        **kwargs: Unpack[WorkerOptions],
    ) -> Worker:
        mageflow_flows = self.init_mageflow_hatchet_tasks()
        workflows += mageflow_flows
        if lifespan is None:
            lifespan = functools.partial(
                lifespan_initialize, self.redis, self._task_defs, self.mageflow_config
            )
        else:
            lifespan = functools.partial(
                merge_lifespan,
                self.redis,
                self._task_defs,
                self.mageflow_config,
                lifespan,
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

    async def chain_end_task(self, msg: ChainCallbackMessage, ctx: Context):
        lifecycle_manager = (
            await ChainTaskSignature.ClientAdapter.lifecycle_from_signature(
                msg, ctx, msg.chain_task_id
            )
        )
        return await chain_end_task(
            msg.chain_results, lifecycle_manager, self.mageflow_logger
        )

    async def chain_error_task(self, msg: ChainErrorMessage, ctx: Context):
        lifecycle_manager = (
            await ChainTaskSignature.ClientAdapter.lifecycle_from_signature(
                msg, ctx, msg.chain_task_id
            )
        )
        return await chain_error_task(
            msg.chain_task_id,
            msg.original_msg,
            msg.error,
            lifecycle_manager,
            self.mageflow_logger,
        )

    async def swarm_item_done(self, msg: SwarmResultsMessage, ctx: Context):
        return await swarm_item_done(
            msg.swarm_task_id,
            msg.swarm_item_id,
            msg.mageflow_results,
            self.mageflow_logger,
        )

    async def swarm_item_failed(self, msg: SwarmErrorMessage, ctx: Context):
        return await swarm_item_failed(
            msg.swarm_task_id, msg.swarm_item_id, msg.error, self.mageflow_logger
        )

    async def fill_swarm_running_tasks(self, msg: FillSwarmMessage, ctx: Context):
        lifecycle = await SwarmTaskSignature.ClientAdapter.lifecycle_from_signature(
            msg, ctx, msg.swarm_task_id
        )
        return await fill_swarm_running_tasks(
            msg.swarm_task_id, msg.max_tasks, lifecycle, self.mageflow_logger
        )
