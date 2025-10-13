import functools
import inspect
from enum import Enum
from typing import Any

from pydantic import BaseModel

from orchestrator.utils.async_calls import flexible_call


class AcceptParams(Enum):
    JUST_MESSAGE = 1
    NO_CTX = 2
    ALL = 3


class HatchetResult(BaseModel):
    hatchet_results: Any


def handle_task_callback(expected_params: AcceptParams = AcceptParams.NO_CTX):
    def task_decorator(func):
        @functools.wraps(func)
        async def wrapper(message: CommandTaskMessage, ctx, *args, **kwargs):
            hatchet = orchestrator_config.hatchet_client
            redis = orchestrator_config.redis_client
            if hatchet is None or redis is None:
                raise ValueError("Orchestrator was not initialized")

            try:
                if not await message.metadata.should_run_task(message):
                    return {}
                if expected_params == AcceptParams.JUST_MESSAGE:
                    result = await flexible_call(func, message)
                elif expected_params == AcceptParams.NO_CTX:
                    result = await flexible_call(func, message, *args, **kwargs)
                else:
                    result = await flexible_call(func, message, ctx, *args, **kwargs)
            except Exception as e:
                has_error_handling = await message.metadata.run_error(message)
                await message.metadata.remove_task(with_error=False)
                if not has_error_handling:
                    raise e
            else:
                await message.metadata.run_success(result, message)
                await message.metadata.remove_task(with_success=False)
                return HatchetResult(hatchet_results=result)

        wrapper.__signature__ = inspect.signature(func)
        return wrapper

    return task_decorator


def register_task(register_name: str = None):
    def decorator(func):
        func.__orchestrator_task_name__ = register_name
        return func

    return decorator
