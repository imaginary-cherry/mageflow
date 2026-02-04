"""
Task callback handlers - adapter-agnostic version.

This module provides the task wrapper/decorator that handles the Mageflow
task lifecycle (start, success, error, cleanup) in a task-manager-agnostic way.

The key insight is that this module works with:
- TaskExecutionInfo: normalized task metadata (extracted from ctx or message)
- TaskContext: normalized context operations (log, cancel, etc.)
- BaseInvoker: task lifecycle management

The adapter is responsible for creating these normalized objects from its
native context/message format.
"""
import asyncio
import functools
import inspect
from enum import Enum
from typing import Any, Callable, TYPE_CHECKING

from pydantic import BaseModel

from mageflow.adapters.protocols import TaskExecutionInfo, TaskContext
from mageflow.invokers.base import BaseInvoker
from mageflow.task.model import TaskModel
from mageflow.utils.pythonic import flexible_call

if TYPE_CHECKING:
    from mageflow.adapters.protocols import TaskManagerAdapter


class AcceptParams(Enum):
    """
    Defines what parameters are passed to user task functions.

    JUST_MESSAGE: func(msg)
    NO_CTX: func(msg, *args, **kwargs) - no context param
    ALL: func(msg, ctx, *args, **kwargs) - full context
    """

    JUST_MESSAGE = 1
    NO_CTX = 2
    ALL = 3


class MageflowResult(BaseModel):
    """Wrapper for task results to ensure consistent serialization."""

    mageflow_results: Any


def create_task_callback_handler(
    adapter: "TaskManagerAdapter",
    invoker_factory: Callable[..., BaseInvoker],
    expected_params: AcceptParams = AcceptParams.NO_CTX,
    wrap_res: bool = True,
    send_signature: bool = False,
):
    """
    Create a task callback handler for a specific adapter.

    This factory creates a decorator that wraps user task functions with
    Mageflow's task lifecycle management. The handler:

    1. Extracts execution info from the adapter's native context
    2. Creates an invoker for task lifecycle management
    3. Checks if the task should run
    4. Executes the user function with appropriate parameters
    5. Handles success/error callbacks

    Args:
        adapter: The task manager adapter
        invoker_factory: Factory function to create invokers
        expected_params: What parameters to pass to the user function
        wrap_res: Whether to wrap results in MageflowResult
        send_signature: Whether to pass the signature to the user function

    Returns:
        A decorator for task functions
    """

    def task_decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(message: Any, raw_context: Any = None, *args, **kwargs):
            # Extract normalized execution info from the adapter
            execution_info = adapter.extract_execution_info(raw_context, message)
            task_context = adapter.create_task_context(raw_context, message)

            # Create the invoker for task lifecycle management
            invoker = invoker_factory(message, execution_info, task_context)

            # Get task model for retry logic
            task_name = execution_info.task_name
            task_model = await TaskModel.aget(task_name) if task_name else None

            # Check if task should run
            if not await invoker.should_run_task():
                await task_context.cancel()
                await asyncio.sleep(10)
                return {"Error": "Task should have been canceled"}

            try:
                # Start the task (update status)
                signature = await invoker.start_task()

                # Optionally pass signature to user function
                if send_signature:
                    kwargs["signature"] = signature

                # Call user function with appropriate parameters
                if expected_params == AcceptParams.JUST_MESSAGE:
                    result = await flexible_call(func, message)
                elif expected_params == AcceptParams.NO_CTX:
                    result = await flexible_call(func, message, *args, **kwargs)
                else:
                    # Pass the task context (normalized, not raw)
                    result = await flexible_call(
                        func, message, task_context, *args, **kwargs
                    )

            except (Exception, asyncio.CancelledError) as e:
                # Check if we should retry
                should_retry = adapter.should_retry(execution_info, e)
                if task_model:
                    should_retry = should_retry and task_model.should_retry(
                        execution_info.attempt_number, e
                    )

                if not should_retry:
                    if signature:
                        await signature.failed()
                    await invoker.run_error()
                    await invoker.remove_task(with_error=False)
                raise

            else:
                # Success path
                task_results = MageflowResult(mageflow_results=result)
                dumped_results = task_results.model_dump(mode="json")
                await invoker.run_success(dumped_results["mageflow_results"])
                await invoker.remove_task(with_success=False)

                if wrap_res:
                    return task_results
                else:
                    return result

        wrapper.__signature__ = inspect.signature(func)
        return wrapper

    return task_decorator


# Registry for registered tasks (task manager agnostic)
REGISTERED_TASKS: list[tuple[Any, str]] = []


def register_task(register_name: str):
    """
    Decorator to register a task with Mageflow.

    This stores the task/workflow reference along with its Mageflow name
    so it can be looked up later for invocation.

    Args:
        register_name: The Mageflow task name

    Returns:
        Decorator that registers and returns the task
    """

    def decorator(func):
        REGISTERED_TASKS.append((func, register_name))
        return func

    return decorator
