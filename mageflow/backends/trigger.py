"""
Unified task trigger interface.

This provides a common interface for triggering tasks that works
with both Hatchet and TaskIQ backends.
"""
from typing import Any

from pydantic import BaseModel

from mageflow.startup import mageflow_config
from mageflow.backends.protocol import BackendType


async def trigger_task(
    task_name: str,
    input_data: Any,
    task_ctx: dict,
    input_validator: type[BaseModel] | None = None,
    use_return_field: bool = True,
    return_field_name: str | None = None,
    workflow_params: dict | None = None,
) -> Any:
    """
    Trigger a task by name using the configured backend.

    This is the unified entry point for Mageflow to trigger tasks
    regardless of which backend (Hatchet, TaskIQ) is configured.

    Args:
        task_name: Name of the registered task
        input_data: Input to pass to the task
        task_ctx: Mageflow context (contains signature key, etc.)
        input_validator: Optional Pydantic model for validation
        use_return_field: Whether to wrap input in return field
        return_field_name: Name of return value field
        workflow_params: Additional params to merge with input

    Returns:
        Task reference/handle (backend-specific)
    """
    backend_type = mageflow_config.backend_type

    if backend_type == BackendType.HATCHET:
        return await _trigger_hatchet(
            task_name=task_name,
            input_data=input_data,
            task_ctx=task_ctx,
            input_validator=input_validator,
            use_return_field=use_return_field,
            return_field_name=return_field_name,
            workflow_params=workflow_params,
        )
    elif backend_type == BackendType.TASKIQ:
        return await _trigger_taskiq(
            task_name=task_name,
            input_data=input_data,
            task_ctx=task_ctx,
            input_validator=input_validator,
            workflow_params=workflow_params,
        )
    else:
        raise ValueError(f"Unknown backend type: {backend_type}")


async def _trigger_hatchet(
    task_name: str,
    input_data: Any,
    task_ctx: dict,
    input_validator: type[BaseModel] | None,
    use_return_field: bool,
    return_field_name: str | None,
    workflow_params: dict | None,
) -> Any:
    """Trigger task using Hatchet workflow."""
    from mageflow.workflows import MageflowWorkflow

    hatchet_client = mageflow_config.hatchet_client
    if hatchet_client is None:
        raise RuntimeError("Hatchet client not configured")

    workflow = hatchet_client.workflow(
        name=task_name,
        input_validator=input_validator,
    )

    return_field = return_field_name if use_return_field else None
    mageflow_wf = MageflowWorkflow(
        workflow,
        workflow_params=workflow_params or {},
        return_value_field=return_field,
        task_ctx=task_ctx,
    )

    return await mageflow_wf.aio_run_no_wait(input_data)


async def _trigger_taskiq(
    task_name: str,
    input_data: Any,
    task_ctx: dict,
    input_validator: type[BaseModel] | None,
    workflow_params: dict | None,
) -> Any:
    """Trigger task using TaskIQ .kiq()."""
    task_trigger = mageflow_config.task_trigger
    if task_trigger is None:
        raise RuntimeError("TaskIQ task trigger not configured")

    # Merge workflow params with input
    if workflow_params:
        if isinstance(input_data, dict):
            input_data = {**input_data, **workflow_params}
        elif isinstance(input_data, BaseModel):
            input_dict = input_data.model_dump()
            input_dict.update(workflow_params)
            input_data = input_dict

    return await task_trigger.trigger(
        task_name=task_name,
        input_data=input_data,
        task_ctx=task_ctx,
        input_validator=input_validator,
    )


class TaskTriggerWrapper:
    """
    Wrapper that provides workflow-like interface for task triggering.

    This is returned by TaskSignature.workflow() and provides
    the same interface regardless of backend.
    """

    def __init__(
        self,
        task_name: str,
        task_ctx: dict,
        input_validator: type[BaseModel] | None = None,
        workflow_params: dict | None = None,
        return_field_name: str | None = None,
    ):
        self._task_name = task_name
        self._task_ctx = task_ctx
        self._input_validator = input_validator
        self._workflow_params = workflow_params or {}
        self._return_field_name = return_field_name

    async def aio_run_no_wait(self, input_data: Any, **kwargs) -> Any:
        """Trigger the task without waiting."""
        return await trigger_task(
            task_name=self._task_name,
            input_data=input_data,
            task_ctx=self._task_ctx,
            input_validator=self._input_validator,
            return_field_name=self._return_field_name,
            workflow_params=self._workflow_params,
        )

    async def aio_run(self, input_data: Any, **kwargs) -> Any:
        """Trigger the task and wait for result (if supported)."""
        # For now, same as no_wait - waiting for result is backend-specific
        return await self.aio_run_no_wait(input_data, **kwargs)
