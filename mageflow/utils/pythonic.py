import inspect
from typing import Any

ParamValidationType = dict[str, tuple[type, Any]]


def deep_merge(base: dict, updates: dict) -> dict:
    results = base.copy()
    for key, value in updates.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            results[key] = deep_merge(base[key], value)
        else:
            results[key] = value
    return results


async def flexible_call(func, *args, **kwargs):
    if inspect.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    else:
        return func(*args, **kwargs)
