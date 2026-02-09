import asyncio
import functools
import inspect
from enum import Enum
from typing import Any

from pydantic import BaseModel

from mageflow.task.model import MageflowTaskModel
from mageflow.utils.pythonic import flexible_call


class AcceptParams(Enum):
    JUST_MESSAGE = 1
    NO_CTX = 2
    ALL = 3


class MageflowResult(BaseModel):
    # Field name kept as hatchet_results for wire-format backward compatibility
    hatchet_results: Any


# Backward-compatible alias
HatchetResult = MageflowResult


def handle_task_callback(
    expected_params: AcceptParams = AcceptParams.NO_CTX,
    wrap_res: bool = True,
    send_signature: bool = False,
):
    def task_decorator(func):
        @functools.wraps(func)
        async def wrapper(message, ctx, *args, **kwargs):
            from mageflow.startup import mageflow_config

            adapter = mageflow_config.adapter
            invoker = adapter.create_invoker(message, ctx)
            task_name = _extract_task_name(ctx)
            task_model = await MageflowTaskModel.aget(task_name)
            if not await invoker.should_run_task():
                await invoker.cancel_current_task()
                await asyncio.sleep(10)
                # NOTE: This should not run, the task should cancel, but just in case
                return {"Error": "Task should have been canceled"}
            try:
                is_normal_run = invoker.is_vanilla_run()
                signature = await invoker.start_task()
                if send_signature:
                    kwargs["signature"] = signature
                if expected_params == AcceptParams.JUST_MESSAGE:
                    result = await flexible_call(func, message)
                elif expected_params == AcceptParams.NO_CTX:
                    result = await flexible_call(func, message, *args, **kwargs)
                else:
                    result = await flexible_call(func, message, ctx, *args, **kwargs)
            except (Exception, asyncio.CancelledError) as e:
                if is_normal_run:
                    raise
                if not task_model.should_retry(invoker.get_attempt_number(), e):
                    await invoker.task_failed()
                    await signature.failed()
                raise
            else:
                if is_normal_run:
                    return result
                task_results = MageflowResult(hatchet_results=result)
                dumped_results = task_results.model_dump(mode="json")
                await invoker.task_success(dumped_results["hatchet_results"])
                await signature.done()
                if wrap_res:
                    return task_results
                else:
                    return result

        wrapper.__signature__ = inspect.signature(func)
        return wrapper

    return task_decorator


def _extract_task_name(ctx) -> str:
    """Extract the task name from the execution context, regardless of client type."""
    # Hatchet context
    if hasattr(ctx, "action") and hasattr(ctx.action, "job_name"):
        return ctx.action.job_name
    # Temporal activity info
    if hasattr(ctx, "workflow_type"):
        return ctx.workflow_type
    # Generic fallback
    if hasattr(ctx, "task_name"):
        return ctx.task_name
    if isinstance(ctx, dict):
        return ctx.get("task_name", "")
    return ""


def register_task(register_name: str):
    from mageflow.startup import REGISTERED_TASKS

    def decorator(func):
        REGISTERED_TASKS.append((func, register_name))
        return func

    return decorator
