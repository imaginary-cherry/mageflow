"""
Task manager adapter registry.

This module provides a registry for task manager adapters. The registry
allows adapters to be registered by type and retrieved when needed.

The registry is the ONLY place where task manager type checking occurs.
All other code should work with the TaskManagerAdapter protocol.
"""
from typing import Type

from mageflow.adapters.protocols import TaskManagerAdapter, TaskManagerType

# Registry of adapter classes by type
_ADAPTER_REGISTRY: dict[TaskManagerType, Type[TaskManagerAdapter]] = {}


def register_adapter(
    adapter_type: TaskManagerType,
) -> callable:
    """
    Decorator to register an adapter class.

    Example:
        @register_adapter(TaskManagerType.HATCHET)
        class HatchetAdapter(TaskManagerAdapter):
            ...
    """

    def decorator(cls: Type[TaskManagerAdapter]) -> Type[TaskManagerAdapter]:
        _ADAPTER_REGISTRY[adapter_type] = cls
        cls.adapter_type = adapter_type
        return cls

    return decorator


def get_adapter_class(adapter_type: TaskManagerType) -> Type[TaskManagerAdapter]:
    """
    Get the adapter class for a task manager type.

    Raises:
        ValueError: If no adapter is registered for the type
    """
    if adapter_type not in _ADAPTER_REGISTRY:
        registered = list(_ADAPTER_REGISTRY.keys())
        raise ValueError(
            f"No adapter registered for {adapter_type}. "
            f"Registered adapters: {registered}"
        )
    return _ADAPTER_REGISTRY[adapter_type]


def get_adapter(adapter_type: TaskManagerType, **config) -> TaskManagerAdapter:
    """
    Create an adapter instance for a task manager type.

    Args:
        adapter_type: The type of task manager
        **config: Configuration options passed to the adapter constructor

    Returns:
        Configured TaskManagerAdapter instance
    """
    adapter_class = get_adapter_class(adapter_type)
    return adapter_class(**config)


def detect_adapter_type(client: object) -> TaskManagerType | None:
    """
    Detect the adapter type from a native client object.

    This is used by the Mageflow factory when a native client is passed
    to automatically select the right adapter.

    Args:
        client: Native task manager client

    Returns:
        TaskManagerType if detected, None otherwise
    """
    # Check for Hatchet
    client_type_name = type(client).__name__
    client_module = type(client).__module__

    if "hatchet" in client_module.lower() or client_type_name == "Hatchet":
        return TaskManagerType.HATCHET

    if "taskiq" in client_module.lower():
        return TaskManagerType.TASKIQ

    return None


def list_registered_adapters() -> list[TaskManagerType]:
    """List all registered adapter types."""
    return list(_ADAPTER_REGISTRY.keys())
