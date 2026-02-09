import abc
from abc import ABC
from typing import Any

from pydantic import BaseModel


class BaseInvoker(ABC):
    """Per-execution invoker - created for each task invocation to manage its lifecycle."""

    @property
    @abc.abstractmethod
    def task_ctx(self) -> dict:
        pass

    @abc.abstractmethod
    async def start_task(self):
        pass

    @abc.abstractmethod
    async def task_success(self, result: Any):
        pass

    @abc.abstractmethod
    async def task_failed(self):
        pass

    @abc.abstractmethod
    async def should_run_task(self) -> bool:
        pass

    @abc.abstractmethod
    async def wait_task(
        self, task_name: str, msg: BaseModel, validator: type[BaseModel] = None
    ):
        pass

    @abc.abstractmethod
    def is_vanilla_run(self) -> bool:
        pass

    @abc.abstractmethod
    def get_attempt_number(self) -> int:
        pass

    @abc.abstractmethod
    async def cancel_current_task(self):
        """Cancel the currently running task execution via the client."""
        pass

    @abc.abstractmethod
    async def log(self, message: str):
        """Log a message through the client's logging mechanism."""
        pass

    @abc.abstractmethod
    async def refresh_timeout(self, timeout):
        """Extend the execution timeout for the current task."""
        pass


class TaskClientAdapter(ABC):
    """
    Client-level adapter that abstracts the task manager (Hatchet, Temporal, etc.).

    Responsible for:
    - Creating workflow/task definitions
    - Registering tasks with the underlying client
    - Creating workers
    - Building invokers for task executions
    - Running workflows (fire-and-forget or wait-for-result)
    - Creating internal mageflow infrastructure tasks (chain/swarm handlers)
    """

    @abc.abstractmethod
    def task(self, name: str, **kwargs):
        """Return a decorator that registers a task/workflow with the client."""
        pass

    @abc.abstractmethod
    def durable_task(self, name: str, **kwargs):
        """Return a decorator that registers a durable/long-running task with the client."""
        pass

    @abc.abstractmethod
    def worker(self, name: str, **kwargs):
        """Create and return a worker that processes tasks."""
        pass

    @abc.abstractmethod
    def create_invoker(self, message: BaseModel, ctx: Any) -> BaseInvoker:
        """Create an invoker instance for a specific task execution."""
        pass

    @abc.abstractmethod
    async def run_task_no_wait(
        self,
        task_name: str,
        msg: BaseModel,
        task_ctx: dict = None,
        input_validator: type[BaseModel] = None,
        extra_params: dict = None,
        return_value_field: str = None,
    ):
        """
        Trigger a task/workflow without waiting for it to complete.
        Returns a run reference.
        """
        pass

    @abc.abstractmethod
    async def run_task_and_wait(
        self,
        task_name: str,
        msg: BaseModel,
        input_validator: type[BaseModel] = None,
    ):
        """Trigger a task/workflow and block until it completes. Returns the result."""
        pass

    @abc.abstractmethod
    def init_internal_tasks(self) -> list:
        """
        Register and return the internal mageflow infrastructure tasks
        (chain_end, chain_error, swarm_start, swarm_end, swarm_error, swarm_fill).
        """
        pass

    @abc.abstractmethod
    def get_task_name(self, workflow_or_func) -> str:
        """Extract the registered task name from a workflow/function."""
        pass

    @abc.abstractmethod
    def get_input_validator(self, workflow_or_func) -> type[BaseModel] | None:
        """Extract the input validator from a workflow/function."""
        pass

    @abc.abstractmethod
    def get_retries(self, workflow_or_func) -> int | None:
        """Extract the retry count from a workflow/function."""
        pass
