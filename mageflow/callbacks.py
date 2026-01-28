import asyncio
import functools
import inspect
from enum import Enum
from typing import Any, TYPE_CHECKING

from pydantic import BaseModel

from mageflow.backends.base import BackendType
from mageflow.task.model import HatchetTaskModel
from mageflow.utils.pythonic import flexible_call

if TYPE_CHECKING:
    from hatchet_sdk import Context
    from hatchet_sdk.runnables.types import EmptyModel
    from hatchet_sdk.runnables.workflow import Standalone


class AcceptParams(Enum):
    JUST_MESSAGE = 1
    NO_CTX = 2
    ALL = 3


class TaskResult(BaseModel):
    """Generic result wrapper for task outputs."""

    task_results: Any


# Backwards compatibility alias
HatchetResult = TaskResult


def get_invoker_for_backend(backend_type: BackendType, message: BaseModel, ctx: Any):
    """
    Get the appropriate invoker for the given backend type.

    Args:
        backend_type: The type of backend (HATCHET or TASKIQ)
        message: The input message
        ctx: The backend-specific context

    Returns:
        An appropriate invoker instance
    """
    if backend_type == BackendType.HATCHET:
        from mageflow.invokers.hatchet import HatchetInvoker

        return HatchetInvoker(message, ctx)
    elif backend_type == BackendType.TASKIQ:
        from mageflow.invokers.taskiq import TaskIQInvoker
        from mageflow.backends.taskiq import TaskIQBackend

        # Convert raw context to TaskContext if needed
        if hasattr(ctx, "additional_metadata"):
            # Already a TaskContext or compatible
            return TaskIQInvoker(message, ctx)
        else:
            # Create TaskContext from TaskIQ context
            backend = TaskIQBackend(None)  # Temporary for context creation
            task_ctx = backend.create_task_context(message, ctx)
            return TaskIQInvoker(message, task_ctx)
    else:
        raise ValueError(f"Unsupported backend type: {backend_type}")


def handle_task_callback(
    expected_params: AcceptParams = AcceptParams.NO_CTX,
    wrap_res: bool = True,
    send_signature: bool = False,
    backend_type: BackendType = BackendType.HATCHET,
):
    """
    Decorator factory for handling task callbacks with MageFlow integration.

    This decorator wraps task functions to:
    - Check if the task should run (respecting pause/suspend)
    - Mark tasks as active when they start
    - Handle success and error callbacks
    - Clean up task state after completion

    Args:
        expected_params: What parameters the task function expects
        wrap_res: Whether to wrap the result in a TaskResult
        send_signature: Whether to pass the TaskSignature to the function
        backend_type: The backend type for invoker selection

    Returns:
        A decorator function
    """

    def task_decorator(func):
        @functools.wraps(func)
        async def wrapper(message: BaseModel, ctx: Any, *args, **kwargs):
            # Get the appropriate invoker based on backend type
            invoker = get_invoker_for_backend(backend_type, message, ctx)

            # Get task model for retry configuration
            job_name = _get_job_name(ctx, backend_type)
            task_model = await HatchetTaskModel.get(job_name)

            # Check if task should run (respects pause/suspend)
            if not await invoker.should_run_task():
                await _cancel_task(ctx, backend_type)
                await asyncio.sleep(10)
                # NOTE: This should not run, the task should cancel, but just in case
                return {"Error": "Task should have been canceled"}

            try:
                signature = await invoker.start_task()
                if send_signature:
                    kwargs["signature"] = signature

                # Call the user function with appropriate parameters
                if expected_params == AcceptParams.JUST_MESSAGE:
                    result = await flexible_call(func, message)
                elif expected_params == AcceptParams.NO_CTX:
                    result = await flexible_call(func, message, *args, **kwargs)
                else:
                    result = await flexible_call(func, message, ctx, *args, **kwargs)

            except (Exception, asyncio.CancelledError) as e:
                # Handle errors
                attempt_number = _get_attempt_number(ctx, backend_type)
                if not task_model.should_retry(attempt_number, e):
                    await invoker.run_error()
                    await invoker.remove_task(with_error=False)
                raise

            else:
                # Handle success
                task_results = TaskResult(task_results=result)
                dumped_results = task_results.model_dump(mode="json")
                await invoker.run_success(dumped_results["task_results"])
                await invoker.remove_task(with_success=False)

                if wrap_res:
                    return task_results
                else:
                    return result

        wrapper.__signature__ = inspect.signature(func)
        return wrapper

    return task_decorator


def _get_job_name(ctx: Any, backend_type: BackendType) -> str:
    """Get the job/task name from context based on backend type."""
    if backend_type == BackendType.HATCHET:
        return ctx.action.job_name
    elif backend_type == BackendType.TASKIQ:
        if hasattr(ctx, "message") and hasattr(ctx.message, "task_name"):
            return ctx.message.task_name
        if hasattr(ctx, "task_name"):
            return ctx.task_name
        return ""
    return ""


def _get_attempt_number(ctx: Any, backend_type: BackendType) -> int:
    """Get the attempt number from context based on backend type."""
    if backend_type == BackendType.HATCHET:
        return ctx.attempt_number
    elif backend_type == BackendType.TASKIQ:
        if hasattr(ctx, "attempt"):
            return ctx.attempt
        if hasattr(ctx, "attempt_number"):
            return ctx.attempt_number
        return 1
    return 1


async def _cancel_task(ctx: Any, backend_type: BackendType) -> None:
    """Cancel the task based on backend type."""
    if backend_type == BackendType.HATCHET:
        await ctx.aio_cancel()
    elif backend_type == BackendType.TASKIQ:
        if hasattr(ctx, "aio_cancel"):
            await ctx.aio_cancel()
        elif hasattr(ctx, "cancel"):
            ctx.cancel()


def register_task(register_name: str):
    """
    Register a task with MageFlow for startup initialization.

    Args:
        register_name: The name to register the task under

    Returns:
        A decorator function
    """
    from mageflow.startup import REGISTERED_TASKS

    def decorator(func):
        REGISTERED_TASKS.append((func, register_name))
        return func

    return decorator
