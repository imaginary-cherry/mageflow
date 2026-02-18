from enum import Enum
from typing import ClassVar

from rapyer import AtomicRedisModel
from rapyer.config import RedisConfig


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
    worker_task_id: str = ""
    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=24 * 60 * 60, refresh_ttl=False)

    def is_canceled(self):
        return self.status in [SignatureStatus.CANCELED]

    def should_run(self):
        return self.status in [SignatureStatus.PENDING, SignatureStatus.ACTIVE]
