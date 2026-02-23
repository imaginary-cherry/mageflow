"""Unit tests for mageflow_mcp.adapters.base — verify ABC enforcement."""
from __future__ import annotations

import pytest

from mageflow_mcp.adapters.base import BaseMCPAdapter
from mageflow_mcp.models import LogEntry


def test__base_mcp_adapter__subclass_without_get_logs__raises_type_error() -> None:
    """A subclass that does not implement get_logs must raise TypeError on instantiation."""

    class IncompleteAdapter(BaseMCPAdapter):
        pass

    with pytest.raises(TypeError):
        IncompleteAdapter()


def test__base_mcp_adapter__subclass_with_get_logs__instantiates_correctly() -> None:
    """A subclass that implements get_logs must instantiate without error."""

    class ConcreteAdapter(BaseMCPAdapter):
        async def get_logs(self, task_run_id: str) -> list[LogEntry]:
            return []

    adapter = ConcreteAdapter()
    assert isinstance(adapter, BaseMCPAdapter)


def test__base_mcp_adapter__is_abstract() -> None:
    """BaseMCPAdapter itself must not be directly instantiable."""
    with pytest.raises(TypeError):
        BaseMCPAdapter()
