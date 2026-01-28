"""
Base abstract interfaces for backend implementations.

This module defines the abstract contracts that all backend implementations
must follow, enabling a unified API across Hatchet, TaskIQ, and other backends.
"""

import abc
from abc import ABC
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, TypeVar, Generic, Protocol, runtime_checkable

from pydantic import BaseModel


class BackendType(str, Enum):
    """Supported backend types."""

    HATCHET = "hatchet"
    TASKIQ = "taskiq"


@dataclass
class TaskContext:
    """
    Unified task context that abstracts backend-specific context objects.

    This class provides a common interface for accessing task execution
    metadata regardless of the underlying backend.
    """

    task_id: str | None = None
    workflow_id: str | None = None
    attempt_number: int = 1
    additional_metadata: dict = field(default_factory=dict)
    raw_context: Any = None  # Backend-specific context object

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get a value from additional metadata."""
        return self.additional_metadata.get(key, default)

    def set_metadata(self, key: str, value: Any) -> None:
        """Set a value in additional metadata."""
        self.additional_metadata[key] = value


@runtime_checkable
class WorkflowWrapper(Protocol):
    """
    Protocol for workflow execution wrappers.

    All backend implementations must provide workflow objects that
    conform to this protocol for unified execution.
    """

    async def aio_run_no_wait(self, input: Any, options: dict | None = None) -> Any:
        """Execute workflow without waiting for completion."""
        ...

    async def aio_run(self, input: Any, options: dict | None = None) -> Any:
        """Execute workflow and wait for completion."""
        ...

    def run_no_wait(self, input: Any, options: dict | None = None) -> Any:
        """Synchronously trigger workflow without waiting."""
        ...

    def run(self, input: Any, options: dict | None = None) -> Any:
        """Synchronously trigger workflow and wait for completion."""
        ...


@runtime_checkable
class WorkerWrapper(Protocol):
    """
    Protocol for worker wrappers.

    All backend implementations must provide worker objects that
    conform to this protocol.
    """

    async def start(self) -> None:
        """Start the worker."""
        ...

    async def stop(self) -> None:
        """Stop the worker."""
        ...


TClient = TypeVar("TClient")


class BackendClient(ABC, Generic[TClient]):
    """
    Abstract base class for backend client implementations.

    This class defines the contract that all backend implementations
    must follow to enable a unified MageFlow API.
    """

    backend_type: BackendType
    _native_client: TClient

    def __init__(self, native_client: TClient):
        self._native_client = native_client

    @property
    def native_client(self) -> TClient:
        """Access the underlying native client."""
        return self._native_client

    @abc.abstractmethod
    def create_workflow(
        self,
        name: str,
        input_validator: type[BaseModel] | None = None,
        workflow_params: dict | None = None,
        return_value_field: str | None = None,
        task_ctx: dict | None = None,
    ) -> WorkflowWrapper:
        """
        Create a workflow wrapper for the given task name.

        Args:
            name: The name of the workflow/task
            input_validator: Optional Pydantic model for input validation
            workflow_params: Additional parameters to merge with workflow input
            return_value_field: Field name for return value wrapping
            task_ctx: Task context metadata to pass through execution

        Returns:
            A WorkflowWrapper that can be used to execute the workflow
        """
        pass

    @abc.abstractmethod
    def create_task_decorator(
        self,
        name: str | None = None,
        input_validator: type[BaseModel] | None = None,
        retries: int = 0,
        **kwargs,
    ) -> Callable:
        """
        Create a task decorator for registering task functions.

        Args:
            name: Task name (defaults to function name)
            input_validator: Optional Pydantic model for input validation
            retries: Number of retry attempts
            **kwargs: Backend-specific options

        Returns:
            A decorator function
        """
        pass

    @abc.abstractmethod
    def create_durable_task_decorator(
        self,
        name: str | None = None,
        input_validator: type[BaseModel] | None = None,
        retries: int = 0,
        **kwargs,
    ) -> Callable:
        """
        Create a durable task decorator for long-running tasks.

        Args:
            name: Task name (defaults to function name)
            input_validator: Optional Pydantic model for input validation
            retries: Number of retry attempts
            **kwargs: Backend-specific options

        Returns:
            A decorator function
        """
        pass

    @abc.abstractmethod
    def create_worker(
        self,
        workflows: list[Any] | None = None,
        lifespan: Callable | None = None,
        **kwargs,
    ) -> WorkerWrapper:
        """
        Create a worker to process tasks.

        Args:
            workflows: List of workflows to register
            lifespan: Lifecycle management function
            **kwargs: Backend-specific options

        Returns:
            A WorkerWrapper for running the worker
        """
        pass

    @abc.abstractmethod
    def create_task_context(self, message: BaseModel, raw_ctx: Any) -> TaskContext:
        """
        Create a unified TaskContext from backend-specific context.

        Args:
            message: The input message
            raw_ctx: Backend-specific context object

        Returns:
            A unified TaskContext
        """
        pass

    @abc.abstractmethod
    def extract_task_data(self, ctx: TaskContext) -> dict:
        """
        Extract MageFlow task data from the context.

        Args:
            ctx: The unified TaskContext

        Returns:
            Dictionary containing MageFlow task metadata
        """
        pass

    @abc.abstractmethod
    async def cancel_task(self, ctx: TaskContext) -> None:
        """
        Cancel the current task execution.

        Args:
            ctx: The unified TaskContext
        """
        pass

    @abc.abstractmethod
    def get_job_name(self, ctx: TaskContext) -> str:
        """
        Get the job/task name from context.

        Args:
            ctx: The unified TaskContext

        Returns:
            The job/task name
        """
        pass

    @abc.abstractmethod
    def log(self, ctx: TaskContext, message: str) -> None:
        """
        Log a message to the backend's logging system.

        Args:
            ctx: The unified TaskContext
            message: The message to log
        """
        pass

    @abc.abstractmethod
    def refresh_timeout(self, ctx: TaskContext, seconds: float) -> None:
        """
        Refresh/extend the task timeout.

        Args:
            ctx: The unified TaskContext
            seconds: Additional seconds to add to timeout
        """
        pass

    @abc.abstractmethod
    def init_mageflow_tasks(self) -> list[Any]:
        """
        Initialize MageFlow internal tasks (chain, swarm handlers).

        Returns:
            List of registered internal workflows/tasks
        """
        pass
