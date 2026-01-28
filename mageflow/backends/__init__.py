"""
Backend abstraction layer for MageFlow.

This module provides a unified interface for different task queue backends
(Hatchet, TaskIQ, etc.) through dependency injection.
"""

from mageflow.backends.base import (
    BackendClient,
    BackendType,
    WorkflowWrapper,
    WorkerWrapper,
    TaskContext,
)

__all__ = [
    "BackendClient",
    "BackendType",
    "WorkflowWrapper",
    "WorkerWrapper",
    "TaskContext",
]
