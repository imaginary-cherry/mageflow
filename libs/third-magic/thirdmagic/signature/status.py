from enum import Enum
from typing import ClassVar

from pydantic import BaseModel
from rapyer import AtomicRedisModel
from rapyer.config import RedisConfig
from rapyer.fields import RapyerKey


class SignatureStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    FAILED = "failed"
    DONE = "done"
    SUSPENDED = "suspended"
    INTERRUPTED = "interrupted"
    CANCELED = "canceled"


class PauseActionTypes(str, Enum):
    SUSPEND = "soft"
    INTERRUPT = "hard"


class TaskStatus(AtomicRedisModel):
    status: SignatureStatus = SignatureStatus.PENDING
    last_status: SignatureStatus = SignatureStatus.PENDING
    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=24 * 60 * 60, refresh_ttl=False)

    def is_canceled(self):
        return self.status in [SignatureStatus.CANCELED]

    def should_run(self):
        return self.status in [SignatureStatus.PENDING, SignatureStatus.ACTIVE]

    def is_done(self):
        return self.status in [SignatureStatus.DONE, SignatureStatus.FAILED]


class ContainerStatus(BaseModel):
    signature_id: RapyerKey
    task_name: str
    status: SignatureStatus
    total: int
    finished: int
    failed: int
    running: int
    pending: int
    percentage: float
    is_done: bool

    @classmethod
    def from_counts(
        cls,
        signature_id: RapyerKey,
        task_name: str,
        status: SignatureStatus,
        total: int,
        finished: int,
        failed: int,
        running: int,
        pending: int,
        is_done: bool,
    ) -> "ContainerStatus":
        percentage = (finished + failed) / total * 100 if total else 0.0
        return cls(
            signature_id=signature_id,
            task_name=task_name,
            status=status,
            total=total,
            finished=finished,
            failed=failed,
            running=running,
            pending=pending,
            percentage=percentage,
            is_done=is_done,
        )


class ContainersStatus(BaseModel):
    containers: list[ContainerStatus]

    @property
    def overall_percentage(self) -> float:
        total = sum(container.total for container in self.containers)
        if not total:
            return 0.0
        terminal = sum(
            container.finished + container.failed for container in self.containers
        )
        return terminal / total * 100
