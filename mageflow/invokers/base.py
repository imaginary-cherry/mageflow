import abc
from abc import ABC
from typing import Any, TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from mageflow.signature.model import TaskSignature
    from mageflow.backends.base import TaskContext


class BaseInvoker(ABC):
    """
    Abstract base class for task invokers.

    Invokers handle the lifecycle of task execution including:
    - Starting tasks and marking them as active
    - Running success/error callbacks
    - Cleaning up task state after completion
    - Determining if a task should run (respecting pause/suspend states)
    """

    def __init__(self, message: BaseModel, ctx: "TaskContext"):
        """
        Initialize the invoker.

        Args:
            message: The input message for the task
            ctx: The unified TaskContext from the backend
        """
        self.message = message
        self.ctx = ctx

    @property
    @abc.abstractmethod
    def task_ctx(self) -> dict:
        """
        Get the task context data (MageFlow metadata).

        Returns:
            Dictionary containing task identifiers and metadata
        """
        pass

    @abc.abstractmethod
    async def start_task(self) -> "TaskSignature | None":
        """
        Mark the task as started in the state store.

        Returns:
            The TaskSignature if found, None otherwise
        """
        pass

    @abc.abstractmethod
    async def run_success(self, result: Any) -> bool:
        """
        Trigger success callbacks for the task.

        Args:
            result: The result of the task execution

        Returns:
            True if callbacks were triggered, False otherwise
        """
        pass

    @abc.abstractmethod
    async def run_error(self) -> bool:
        """
        Trigger error callbacks for the task.

        Returns:
            True if callbacks were triggered, False otherwise
        """
        pass

    @abc.abstractmethod
    async def remove_task(
        self, with_success: bool = True, with_error: bool = True
    ) -> "TaskSignature | None":
        """
        Remove the task from the state store.

        Args:
            with_success: Whether to also remove success callbacks
            with_error: Whether to also remove error callbacks

        Returns:
            The removed TaskSignature if found, None otherwise
        """
        pass

    @abc.abstractmethod
    async def should_run_task(self) -> bool:
        """
        Check if the task should be executed.

        This respects pause/suspend states set on the task.

        Returns:
            True if the task should run, False otherwise
        """
        pass
