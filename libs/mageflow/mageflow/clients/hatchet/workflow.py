from __future__ import annotations

import functools
import inspect
from typing import TYPE_CHECKING, Any

from hatchet_sdk import Context
from hatchet_sdk.runnables.workflow import Workflow
from hatchet_sdk.utils.typing import JSONSerializableMapping
from pydantic import BaseModel
from thirdmagic.task import TaskSignature
from thirdmagic.utils import deep_merge

if TYPE_CHECKING:
    from mageflow.clients.hatchet.mageflow import HatchetMageflow


class MageWorkflow(Workflow):
    """
    We patch the Workflow class to add Mageflow-specific hooks.
    """

    def __init__(self, base_workflow: Workflow, mageflow: "HatchetMageflow"):
        super().__init__(config=base_workflow.config, client=base_workflow.client)
        self.__dict__.update(base_workflow.__dict__)
        self._mageflow = mageflow

    def on_success_task(self, *args, **kwargs):
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
            return task_wrapper

        return wrapper

    def on_failure_task(self, *args, **kwargs):
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
            return task_wrapper

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
