import functools
import inspect
from datetime import timedelta
from typing import Any, TypedDict, Unpack

from hatchet_sdk import Context
from hatchet_sdk.rate_limit import RateLimit
from hatchet_sdk.runnables.types import ConcurrencyExpression
from hatchet_sdk.runnables.workflow import Workflow
from hatchet_sdk.utils.typing import JSONSerializableMapping
from pydantic import BaseModel
from thirdmagic.task import TaskSignature
from thirdmagic.utils import deep_merge

Duration = timedelta | str


class LifecycleTaskOptions(TypedDict, total=False):
    name: str | None
    schedule_timeout: Duration
    execution_timeout: Duration
    retries: int
    rate_limits: list[RateLimit] | None
    backoff_factor: float | None
    backoff_max_seconds: int | None
    concurrency: int | list[ConcurrencyExpression] | None


class MageWorkflow(Workflow):
    """
    We patch the Workflow class to add Mageflow-specific hooks.
    """

    def __init__(self, base_workflow: Workflow):
        super().__init__(config=base_workflow.config, client=base_workflow.client)

    def on_success_task(self, **kwargs: Unpack[LifecycleTaskOptions]):
        parent_decorator = super().on_success_task(**kwargs)

        def wrapper(func):
            @functools.wraps(func)
            async def task_wrapper(
                msg: BaseModel, ctx: Context, *task_args, **task_kwargs
            ):
                lifecycle = await TaskSignature.ClientAdapter.create_lifecycle(msg, ctx)
                is_normal_run = lifecycle.is_vanilla_run()
                if not is_normal_run:
                    await lifecycle.task_success(msg)

                return await func(msg, ctx, *task_args, **task_kwargs)

            task_wrapper.__signature__ = inspect.signature(func)
            return parent_decorator(task_wrapper)

        return wrapper

    def on_failure_task(self, **kwargs: Unpack[LifecycleTaskOptions]):
        parent_decorator = super().on_failure_task(**kwargs)

        def wrapper(func):
            @functools.wraps(func)
            async def task_wrapper(
                msg: BaseModel, ctx: Context, *task_args, **task_kwargs
            ):
                lifecycle = await TaskSignature.ClientAdapter.create_lifecycle(msg, ctx)
                is_normal_run = lifecycle.is_vanilla_run()
                if not is_normal_run:
                    await lifecycle.task_failed(
                        msg.model_dump(mode="json", exclude_unset=True),
                        Exception(str(msg)),
                    )

                return await func(msg, ctx, *task_args, **task_kwargs)

            task_wrapper.__signature__ = inspect.signature(func)
            return parent_decorator(task_wrapper)

        return wrapper


class MageflowWorkflow(Workflow):
    def __init__(
        self,
        workflow: Workflow,
        workflow_params: dict,
        return_value_field: str = None,
    ):
        super().__init__(config=workflow.config, client=workflow.client)
        self._mageflow_workflow_params = workflow_params
        self._return_value_field = return_value_field

    def _serialize_input(self, input: Any) -> JSONSerializableMapping:
        if isinstance(input, BaseModel):
            input = input.model_dump(mode="json")

        # Force model dump
        kwargs = self._mageflow_workflow_params

        if self._return_value_field:
            return_field = {self._return_value_field: input}
        else:
            return_field = input

        full_msg = deep_merge(return_field, kwargs)
        return super(MageflowWorkflow, self)._serialize_input(full_msg)
