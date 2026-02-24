"""Pydantic response models for MCP tool outputs."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from thirdmagic.signature.status import SignatureStatus


class ErrorResponse(BaseModel):
    """Structured error response returned by MCP tools when an operation fails."""

    error: str
    message: str
    suggestion: str


class SignatureInfo(BaseModel):
    """Projected view of a task signature stored in Redis."""

    key: str
    signature_type: str
    task_name: str
    status: SignatureStatus
    creation_time: datetime
    kwargs: dict[str, Any]
    return_value: Any | None = None
    worker_task_id: str | None = None


class ContainerSummary(BaseModel):
    """Sub-task counts for chain/swarm container signatures."""

    container_key: str
    signature_type: str
    total: int
    pending: int
    active: int
    done: int
    failed: int
    suspended: int
    canceled: int


class SubTaskInfo(BaseModel):
    """Minimal sub-task representation for paginated lists."""

    key: str
    task_name: str
    status: SignatureStatus


class LogEntry(BaseModel):
    """Single log line from a task run."""

    line: str
    timestamp: datetime | None = None
    level: str | None = None
    sub_task_id: str | None = None


class LogsResponse(BaseModel):
    """Paginated log line response with run completion status."""

    items: list[LogEntry]
    total_count: int
    page: int
    page_size: int
    total_pages: int
    is_complete: bool
    worker_task_id: str


class TaskDefinitionInfo(BaseModel):
    """Task registry entry from the mageflow task definition store."""

    mageflow_task_name: str
    task_name: str
    retries: int | None = None


class PaginatedSignatureList(BaseModel):
    """Paginated list of signature summaries."""

    items: list[SignatureInfo]
    total_count: int
    page: int
    page_size: int
    total_pages: int


class PaginatedSubTaskList(BaseModel):
    """Paginated list of sub-task summaries."""

    items: list[SubTaskInfo]
    total_count: int
    page: int
    page_size: int
    total_pages: int


class PaginatedTaskDefinitionList(BaseModel):
    """Paginated list of registered task definitions."""

    items: list[TaskDefinitionInfo]
    total_count: int
    page: int
    page_size: int
    total_pages: int
