from typing import ClassVar

from mageflow.signature.types import TaskIdentifierType
from pydantic import Field
from rapyer import AtomicRedisModel
from rapyer.config import RedisConfig
from rapyer.types import RedisList


class PublishState(AtomicRedisModel):
    task_ids: RedisList[TaskIdentifierType] = Field(default_factory=list)

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=24 * 60 * 60, refresh_ttl=False)
