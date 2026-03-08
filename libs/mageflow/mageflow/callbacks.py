import asyncio
import functools
import inspect
from enum import Enum
from typing import Any

from hatchet_sdk import Context
from hatchet_sdk.runnables.types import EmptyModel
from pydantic import BaseModel
from thirdmagic.signature.retry_cache import (
    retry_cache_ctx,
    setup_retry_cache,
    teardown_retry_cache,
)
from thirdmagic.task.model import TaskSignature
from thirdmagic.task_def import MageflowTaskDefinition

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
    is_idempotent: bool = False,
):
    def task_decorator(func):
        @functools.wraps(func)
        async def wrapper(message: EmptyModel, ctx: Context, *args, **kwargs):
            lifecycle = await TaskSignature.ClientAdapter.create_lifecycle(message, ctx)
            task_model = await MageflowTaskDefinition.aget(ctx.workflow_name)
            msg_data = message.model_dump(mode="json", exclude_unset=True)
            if not await lifecycle.should_run_task(msg_data):
                await ctx.aio_cancel()
                await asyncio.sleep(10)
                # NOTE: This should not run, the task should cancel, but just in case
                return {"Error": "Task should have been canceled"}
            is_normal_run = lifecycle.is_vanilla_run()
            is_task_finish = False
            signature = await lifecycle.start_task()

            # Setup retry cache for signature idempotency on retries (durable tasks only)
            cache_token = None
            cache_state = None
            if is_idempotent:
                cache_state = await setup_retry_cache(
                    ctx.workflow_id, ctx.attempt_number
                )
                cache_token = retry_cache_ctx.set(cache_state)

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
            except asyncio.CancelledError as e:
                if not is_normal_run:
                    is_task_finish = True
                    await lifecycle.task_failed(msg_data, e)
                raise
            except Exception as e:
                will_retry = TaskSignature.ClientAdapter.should_task_retry(
                    task_model, ctx.attempt_number, e
                )
                if not will_retry:
                    is_task_finish = True
                    if not is_normal_run:
                        await lifecycle.task_failed(msg_data, e)
                raise
            else:
                # If this is a simple task, no signature, then we dont do any manipulation
                is_task_finish = True
                if is_normal_run:
                    return result
                task_results = HatchetResult(hatchet_results=result)
                dumped_results = task_results.model_dump(mode="json")
                await lifecycle.task_success(dumped_results["hatchet_results"])
                if wrap_res:
                    return task_results
                else:
                    return result
            finally:
                if cache_token is not None:
                    retry_cache_ctx.reset(cache_token)
                if is_task_finish and cache_state:
                    await teardown_retry_cache(cache_state)

        wrapper.__signature__ = inspect.signature(func)
        return wrapper

    return task_decorator
