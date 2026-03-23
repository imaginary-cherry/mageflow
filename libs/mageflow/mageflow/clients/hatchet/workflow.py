from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any

from hatchet_sdk import Context
from hatchet_sdk.runnables.workflow import Workflow
from hatchet_sdk.utils.typing import JSONSerializableMapping
from pydantic import BaseModel
from thirdmagic.utils import deep_merge

if TYPE_CHECKING:
    from mageflow.clients.hatchet.mageflow import HatchetMageflow


class MageWorkflow(Workflow):
    """Workflow subclass that self-injects mageflow lifecycle hooks.

    Created by HatchetMageflow.workflow(). Hooks are injected when
    _inject_hooks() is called (typically by HatchetMageflow.worker()).
    """

    def __init__(self, base_workflow: Workflow, mageflow: "HatchetMageflow"):
        # Copy all state from the base workflow
        super().__init__(config=base_workflow.config, client=base_workflow.client)
        self.__dict__.update(base_workflow.__dict__)
        self._mageflow = mageflow

    async def _lifecycle_from_ctx(self, ctx: Context):
        return await self._mageflow._lifecycle_from_ctx(ctx)

    def _inject_hooks(self) -> None:
        """Inject mageflow lifecycle callbacks into on_success/on_failure slots."""
        # --- on_success_task ---
        if self._on_success_task is None:
            @self.on_success_task()
            @functools.wraps(lambda input, ctx: None)
            async def _mageflow_on_success(input, ctx: Context):
                lifecycle = await self._lifecycle_from_ctx(ctx)
                if lifecycle is not None:
                    await lifecycle.task_success({})
        else:
            original_success_fn = self._on_success_task.fn

            @functools.wraps(original_success_fn)
            async def _composed_success(input, ctx: Context):
                lifecycle = await self._lifecycle_from_ctx(ctx)
                if lifecycle is not None:
                    await lifecycle.task_success({})
                return await original_success_fn(input, ctx)

            self._on_success_task.fn = _composed_success

        # --- on_failure_task ---
        if self._on_failure_task is None:
            @self.on_failure_task()
            @functools.wraps(lambda input, ctx: None)
            async def _mageflow_on_failure(input, ctx: Context):
                lifecycle = await self._lifecycle_from_ctx(ctx)
                if lifecycle is not None:
                    errors = dict(ctx.task_run_errors)
                    await lifecycle.task_failed(errors, Exception(str(errors)))
        else:
            original_failure_fn = self._on_failure_task.fn

            @functools.wraps(original_failure_fn)
            async def _composed_failure(input, ctx: Context):
                lifecycle = await self._lifecycle_from_ctx(ctx)
                if lifecycle is not None:
                    errors = dict(ctx.task_run_errors)
                    await lifecycle.task_failed(errors, Exception(str(errors)))
                return await original_failure_fn(input, ctx)

            self._on_failure_task.fn = _composed_failure


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
