from contextvars import ContextVar
from dataclasses import dataclass
from typing import ClassVar, Optional, Type, TypeVar

from pydantic import Field
from rapyer import AtomicRedisModel
from rapyer.config import RedisConfig
from rapyer.fields import Key, RapyerKey
from rapyer.types import RedisList

from thirdmagic.signature.model import Signature

T = TypeVar("T", bound=Signature)


class SignatureRetryCache(AtomicRedisModel):
    workflow_id: Key[str] = ""
    signature_ids: RedisList[RapyerKey] = Field(default_factory=list)

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=24 * 60 * 60, refresh_ttl=False)


@dataclass
class RetryCacheState:
    workflow_id: str
    is_retry: bool
    cache: SignatureRetryCache
    index: int = 0


retry_cache_ctx: ContextVar[Optional[RetryCacheState]] = ContextVar(
    "retry_cache_ctx", default=None
)


async def setup_retry_cache(workflow_id: str, attempt_number: int) -> RetryCacheState:
    is_retry = attempt_number > 1
    if is_retry:
        cache = await SignatureRetryCache.afind_one(workflow_id)
    else:
        cache = SignatureRetryCache(workflow_id=workflow_id)
        await cache.asave()
    return RetryCacheState(workflow_id=workflow_id, is_retry=is_retry, cache=cache)


async def teardown_retry_cache(state: RetryCacheState):
    await state.cache.adelete()


async def get_cached_signature(sig_type: Type[T]) -> Optional[T]:
    state = retry_cache_ctx.get()
    if not (state and state.is_retry):
        return None
    cache = state.cache
    if state.index >= len(cache.signature_ids):
        return None
    sig_key = cache.signature_ids[state.index]
    state.index += 1
    sig = await sig_type.afind_one(sig_key)
    return sig


async def cache_signature(signature: Signature):
    state = retry_cache_ctx.get()
    if state is None:
        return None
    await state.cache.signature_ids.aappend(signature.key)
    state.index += 1
    return None
