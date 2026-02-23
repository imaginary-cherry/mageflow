"""Pydantic response models for MCP tool outputs."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from thirdmagic.signature.status import SignatureStatus


class SignatureInfo(BaseModel):
    """Projected view of a task signature stored in Redis."""

    key: str
    signature_type: str
    task_name: str
    status: SignatureStatus
    creation_time: datetime
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


class TaskDefinitionInfo(BaseModel):
    """Task registry entry from the mageflow task definition store."""

    mageflow_task_name: str
    task_name: str
    retries: int | None = None
