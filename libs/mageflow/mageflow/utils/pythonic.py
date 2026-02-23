import inspect
from typing import Any

ParamValidationType = dict[str, tuple[type, Any]]


async def flexible_call(func, *args, **kwargs):
    if inspect.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    else:
        return func(*args, **kwargs)
