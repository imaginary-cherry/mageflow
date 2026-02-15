from typing import ClassVar

from pydantic import Field
from rapyer import AtomicRedisModel
from rapyer.config import RedisConfig
from rapyer.fields import RapyerKey
from rapyer.types import RedisList


class PublishState(AtomicRedisModel):
    task_ids: RedisList[RapyerKey] = Field(default_factory=list)

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=24 * 60 * 60, refresh_ttl=False)
