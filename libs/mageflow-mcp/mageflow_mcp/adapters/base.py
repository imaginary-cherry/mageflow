import abc
from abc import ABC

from mageflow_mcp.models import LogEntry


class BaseMCPAdapter(ABC):
    @abc.abstractmethod
    async def get_logs(self, task_run_id: str) -> list[LogEntry]:
        """
        Retrieve log entries for a given backend task run ID.

        Args:
            task_run_id: The backend-specific identifier for the task run.
                         Format is backend-dependent (e.g., Hatchet run UUID).

        Returns:
            List of LogEntry objects in chronological order.
            Returns an empty list if the run ID is missing or logs have expired.
            Never returns None.

        Raises:
            Exception: MAY raise for infrastructure failures (e.g., network
                       timeout, backend unavailable). Does NOT raise for
                       missing or expired run IDs — return empty list instead.
        """

    @abc.abstractmethod
    async def get_run_status(self, task_run_id: str) -> str:
        """
        Return the backend run status as a string.

        Expected values: 'QUEUED', 'RUNNING', 'COMPLETED', 'CANCELLED', 'FAILED'.
        Return 'RUNNING' if the status cannot be determined — this is the safe
        non-terminal default that avoids marking a log stream as complete prematurely.

        Args:
            task_run_id: The backend-specific identifier for the task run.

        Returns:
            A string status value. Safe to compare against terminal status set.
        """
