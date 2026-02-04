"""
Backend implementations for different task managers.

This module provides internal implementations for Mageflow to work with
different task managers. The abstraction is MINIMAL - only covering what
Mageflow needs internally:

1. TaskTrigger: How to trigger a task by name with metadata
2. ExecutionContext: How to extract metadata from running tasks

The user-facing API is NOT abstracted - each backend (Hatchet, TaskIQ)
exposes its native API plus Mageflow additions (sign, swarm, chain).
"""
from mageflow.backends.protocol import (
    TaskTrigger,
    ExecutionContext,
    BackendType,
)

__all__ = [
    "TaskTrigger",
    "ExecutionContext",
    "BackendType",
]
