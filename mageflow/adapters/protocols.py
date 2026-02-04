"""
Protocol interfaces for task manager abstraction.

This module defines the contracts that any task manager (Hatchet, TaskIQ, etc.)
must implement to work with Mageflow. The key principle is that all task-manager
specific code is isolated to adapter implementations, and the core Mageflow code
only uses these protocol interfaces.

Key Concepts:
- TaskManagerAdapter: Main client interface for creating tasks, workers, workflows
- TaskContext: Abstraction over the context object passed to task functions (e.g., Hatchet's ctx)
- TaskExecutionInfo: Task-manager-agnostic data extracted from context
- WorkflowAdapter: Interface for triggering workflows
- WorkerAdapter: Interface for worker management
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum, auto
from typing import (
    Any,
    Callable,
    TypeVar,
    Generic,
    Awaitable,
    Protocol,
    runtime_checkable,
    TypedDict,
)

from pydantic import BaseModel


class TaskManagerType(Enum):
    """Supported task manager types."""

    HATCHET = auto()
    TASKIQ = auto()


@dataclass
class TaskExecutionInfo:
    """
    Task-manager-agnostic execution information.

    This is extracted from the task manager's context object and provides
    a unified interface for accessing task execution metadata.
    """

    task_data: dict = field(default_factory=dict)
    """Custom metadata passed with the task (e.g., signature key)"""

    workflow_id: str | None = None
    """Unique identifier for this workflow/task execution"""

    task_name: str | None = None
    """Name of the current task being executed"""

    attempt_number: int = 1
    """Current retry attempt number (1-indexed)"""

    raw_context: Any = None
    """Original context object from the task manager (for advanced use cases)"""


@runtime_checkable
class TaskContext(Protocol):
    """
    Protocol for task execution context.

    This abstracts the context object passed to task functions by different
    task managers. Each adapter must provide an implementation that wraps
    the native context and exposes these common operations.
    """

    @property
    def execution_info(self) -> TaskExecutionInfo:
        """Get task execution information extracted from the context."""
        ...

    def log(self, message: str) -> None:
        """Log a message associated with this task execution."""
        ...

    async def cancel(self) -> None:
        """Request cancellation of this task."""
        ...

    def refresh_timeout(self, duration: timedelta) -> None:
        """Extend the task execution timeout."""
        ...


@runtime_checkable
class WorkflowAdapter(Protocol):
    """
    Protocol for workflow execution.

    Abstracts workflow triggering across different task managers.
    """

    async def aio_run(
        self,
        input: Any = None,
        options: dict | None = None,
    ) -> Any:
        """Run the workflow and wait for result."""
        ...

    async def aio_run_no_wait(
        self,
        input: Any = None,
        options: dict | None = None,
    ) -> Any:
        """Trigger the workflow without waiting for result."""
        ...

    def run(
        self,
        input: Any = None,
        options: dict | None = None,
    ) -> Any:
        """Synchronously run the workflow and wait for result."""
        ...

    def run_no_wait(
        self,
        input: Any = None,
        options: dict | None = None,
    ) -> Any:
        """Synchronously trigger the workflow without waiting for result."""
        ...


@runtime_checkable
class WorkerAdapter(Protocol):
    """Protocol for worker management."""

    async def async_start(self) -> None:
        """Start the worker asynchronously."""
        ...

    def start(self) -> None:
        """Start the worker synchronously."""
        ...


class TaskOptions(TypedDict, total=False):
    """
    Task configuration options.

    These are normalized options that work across task managers.
    Each adapter is responsible for translating these to its native format.
    """

    name: str | None
    """Task name/identifier"""

    description: str | None
    """Human-readable task description"""

    input_validator: type | None
    """Pydantic model for input validation"""

    retries: int
    """Number of retry attempts"""

    execution_timeout: timedelta | str
    """Maximum execution time"""

    schedule_timeout: timedelta | str
    """Maximum time to wait for scheduling"""

    concurrency_key: str | None
    """Expression for concurrency grouping"""

    concurrency_limit: int | None
    """Maximum concurrent executions"""

    on_events: list[str] | None
    """Events that trigger this task"""

    on_crons: list[str] | None
    """Cron schedules for this task"""

    default_priority: int
    """Default execution priority"""

    durable: bool
    """Whether task survives worker restarts"""

    backoff_factor: float | None
    """Exponential backoff multiplier for retries"""

    backoff_max_seconds: int | None
    """Maximum backoff time in seconds"""


class WorkerOptions(TypedDict, total=False):
    """Worker configuration options."""

    slots: int
    """Number of concurrent task slots"""

    durable_slots: int
    """Number of durable task slots"""

    labels: dict[str, str | int] | None
    """Worker labels for routing"""


# Type variable for task function
TaskFunc = TypeVar("TaskFunc", bound=Callable[..., Awaitable[Any]])


class TaskManagerAdapter(ABC):
    """
    Abstract base class for task manager adapters.

    Each task manager (Hatchet, TaskIQ, etc.) must provide a concrete
    implementation of this adapter. The adapter is responsible for:

    1. Creating and configuring the native client
    2. Providing task decorators that wrap functions appropriately
    3. Creating workers with correct configuration
    4. Creating workflow adapters for triggering tasks
    5. Extracting TaskExecutionInfo from native context objects

    Example usage (from Mageflow factory):
        adapter = HatchetAdapter(config)
        mageflow = MageflowClient(adapter)
    """

    adapter_type: TaskManagerType

    @abstractmethod
    def task(
        self,
        name: str | None = None,
        **options: Any,
    ) -> Callable[[TaskFunc], TaskFunc]:
        """
        Create a task decorator.

        The decorator should:
        1. Register the task with the task manager
        2. Wrap the function to receive normalized parameters
        3. Handle the task lifecycle (start, success, error)

        Args:
            name: Task name (defaults to function name)
            **options: Task configuration options

        Returns:
            A decorator that wraps the task function
        """
        pass

    @abstractmethod
    def durable_task(
        self,
        name: str | None = None,
        **options: Any,
    ) -> Callable[[TaskFunc], TaskFunc]:
        """
        Create a durable task decorator.

        Durable tasks survive worker restarts. The implementation details
        vary by task manager.
        """
        pass

    @abstractmethod
    def worker(
        self,
        name: str,
        workflows: list[Any] | None = None,
        lifespan: Callable | None = None,
        **options: Any,
    ) -> WorkerAdapter:
        """
        Create a worker that processes tasks.

        Args:
            name: Worker name
            workflows: List of workflow/task definitions to run
            lifespan: Async context manager for worker lifecycle
            **options: Additional worker options

        Returns:
            A worker adapter that can be started
        """
        pass

    @abstractmethod
    def workflow(
        self,
        name: str,
        input_validator: type[BaseModel] | None = None,
        task_ctx: dict | None = None,
        workflow_params: dict | None = None,
        return_value_field: str | None = None,
    ) -> WorkflowAdapter:
        """
        Create a workflow adapter for triggering tasks.

        Args:
            name: Workflow/task name to trigger
            input_validator: Pydantic model for input validation
            task_ctx: Mageflow task context (signature key, etc.)
            workflow_params: Additional parameters to merge with input
            return_value_field: Field name for return value mapping

        Returns:
            A workflow adapter for triggering the task
        """
        pass

    @abstractmethod
    def extract_execution_info(self, raw_context: Any, message: Any) -> TaskExecutionInfo:
        """
        Extract normalized execution info from native context.

        This is called by the task wrapper to get a TaskExecutionInfo
        from the native context object (e.g., Hatchet's Context).

        Args:
            raw_context: Native context object from the task manager
            message: The message/input passed to the task

        Returns:
            Normalized TaskExecutionInfo
        """
        pass

    @abstractmethod
    def create_task_context(self, raw_context: Any, message: Any) -> TaskContext:
        """
        Create a TaskContext wrapper for the native context.

        This creates a normalized context wrapper that task functions
        can use for logging, cancellation, etc.

        Args:
            raw_context: Native context object from the task manager
            message: The message/input passed to the task

        Returns:
            TaskContext wrapper
        """
        pass

    @abstractmethod
    def create_framework_tasks(self) -> list[Any]:
        """
        Create internal framework tasks (chain, swarm handlers).

        These are the internal tasks that handle chain/swarm callbacks.
        Each task manager implements these according to its patterns.

        Returns:
            List of framework task/workflow definitions
        """
        pass

    @abstractmethod
    def should_retry(self, execution_info: TaskExecutionInfo, exception: Exception) -> bool:
        """
        Determine if a task should be retried after an exception.

        Args:
            execution_info: Current task execution info
            exception: The exception that occurred

        Returns:
            True if the task should be retried
        """
        pass

    @property
    @abstractmethod
    def native_client(self) -> Any:
        """Get the native task manager client."""
        pass


class InvokerFactory(Protocol):
    """
    Protocol for creating invokers.

    The invoker handles task lifecycle management (start, success, error).
    This factory creates the appropriate invoker based on the adapter type.
    """

    def create_invoker(
        self,
        message: Any,
        execution_info: TaskExecutionInfo,
        task_context: TaskContext,
    ) -> "BaseInvokerProtocol":
        """Create an invoker for the task execution."""
        ...


@runtime_checkable
class BaseInvokerProtocol(Protocol):
    """Protocol matching the BaseInvoker interface."""

    @property
    def task_ctx(self) -> dict:
        """Get task context/metadata."""
        ...

    async def start_task(self) -> Any:
        """Mark task as started."""
        ...

    async def run_success(self, result: Any) -> bool:
        """Handle successful task completion."""
        ...

    async def run_error(self) -> bool:
        """Handle task error."""
        ...

    async def remove_task(
        self, with_success: bool = True, with_error: bool = True
    ) -> Any:
        """Clean up task."""
        ...

    async def should_run_task(self) -> bool:
        """Determine if task should execute."""
        ...

    async def wait_task(
        self, task_name: str, msg: BaseModel, validator: type[BaseModel] | None = None
    ) -> Any:
        """Wait for another task."""
        ...
