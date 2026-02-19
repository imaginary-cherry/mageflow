import asyncio
import functools
import inspect
from enum import Enum
from typing import Any

from hatchet_sdk import Context
from hatchet_sdk.runnables.types import EmptyModel
from hatchet_sdk.runnables.workflow import Standalone
from pydantic import BaseModel
from thirdmagic.task.model import TaskSignature
from thirdmagic.task_def import MageflowTaskDefinition

from mageflow.lifecycle.task import TaskLifecycle
from mageflow.utils.pythonic import flexible_call


class AcceptParams(Enum):
    JUST_MESSAGE = 1
    NO_CTX = 2
    ALL = 3


class HatchetResult(BaseModel):
    hatchet_results: Any


def handle_task_callback(
    expected_params: AcceptParams = AcceptParams.NO_CTX,
    wrap_res: bool = True,
    send_signature: bool = False,
):
    def task_decorator(func):
        @functools.wraps(func)
        async def wrapper(message: EmptyModel, ctx: Context, *args, **kwargs):
            lifecycle = await TaskSignature.ClientAdapter.create_lifecycle(message, ctx)
            task_model = await MageflowTaskDefinition.aget(ctx.action.job_name)
            if not await lifecycle.should_run_task(message):
                await ctx.aio_cancel()
                await asyncio.sleep(10)
                # NOTE: This should not run, the task should cancel, but just in case
                return {"Error": "Task should have been canceled"}
            is_normal_run = lifecycle.is_vanilla_run()
            signature = await lifecycle.start_task()

            # Add params if user requires
            if send_signature:
                kwargs["signature"] = signature

            try:
                if expected_params == AcceptParams.JUST_MESSAGE:
                    result = await flexible_call(func, message)
                elif expected_params == AcceptParams.NO_CTX:
                    result = await flexible_call(func, message, *args, **kwargs)
                else:
                    result = await flexible_call(func, message, ctx, *args, **kwargs)
            except (Exception, asyncio.CancelledError) as e:
                if is_normal_run:
                    raise
                if not TaskSignature.ClientAdapter.should_task_retry(
                    task_model, ctx.attempt_number, e
                ):
                    await lifecycle.task_failed(message, e)
                raise
            else:
                # If this is a simple task, no signature, then we dont do any manipulation
                if is_normal_run:
                    return result
                task_results = HatchetResult(hatchet_results=result)
                dumped_results = task_results.model_dump(mode="json")
                await lifecycle.task_success(dumped_results["hatchet_results"])
                if wrap_res:
                    return task_results
                else:
                    return result

        wrapper.__signature__ = inspect.signature(func)
        return wrapper

    return task_decorator


def register_task(register_name: str):
    from mageflow.startup import REGISTERED_TASKS

    def decorator(func: Standalone):
        REGISTERED_TASKS.append((func, register_name))
        return func

    return decorator
