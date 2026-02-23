"""Base adapter ABC for MCP observation clients.

This module defines the adapter interface for plugging in backend-specific
log retrieval. BaseMCPAdapter is a sibling to BaseClientAdapter (from
thirdmagic) — it is NOT a subclass. BaseMCPAdapter is for observation
(read-only log access), while BaseClientAdapter is for orchestration
(task publishing and management). These are parallel hierarchies with
distinct responsibilities.
"""
from __future__ import annotations

import abc
from abc import ABC

from mageflow_mcp.models import LogEntry


class BaseMCPAdapter(ABC):
    """Abstract base class for MCP backend adapters.

    Implementations provide log retrieval from a specific backend (e.g.,
    Hatchet). This class is intentionally minimal: Phase 3 will add the
    HatchetMCPAdapter as the first concrete implementation.
    """

    @abc.abstractmethod
    async def get_logs(self, task_run_id: str) -> list[LogEntry]:
        """Retrieve log entries for a given backend task run ID.

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
