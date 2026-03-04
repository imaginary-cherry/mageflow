from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import ClassVar, Optional, TypeVar, Type, cast

import rapyer
from pydantic import Field
from rapyer import AtomicRedisModel
from rapyer.config import RedisConfig
from rapyer.fields import RapyerKey
from rapyer.types import RedisList

from thirdmagic.signature.model import Signature

T = TypeVar("T", bound=Signature)


class SignatureRetryCache(AtomicRedisModel):
    workflow_id: str = ""
    signature_ids: RedisList[RapyerKey] = Field(default_factory=list)

    Meta: ClassVar[RedisConfig] = RedisConfig(
        ttl=24 * 60 * 60,
        refresh_ttl=False,
    )


@dataclass
class RetryCacheState:
    workflow_id: str
    is_retry: bool
    cache: Optional[SignatureRetryCache] = None
    index: int = 0


retry_cache_ctx: ContextVar[Optional[RetryCacheState]] = ContextVar(
    "retry_cache_ctx", default=None
)


async def setup_retry_cache(
    workflow_id: str, attempt_number: int
) -> RetryCacheState:
    is_retry = attempt_number > 1
    if is_retry:
        try:
            redis_key = f"SignatureRetryCache:{workflow_id}"
            cache = await rapyer.aget(redis_key)
        except Exception:
            cache = None
        if cache:
            return RetryCacheState(
                workflow_id=workflow_id,
                is_retry=True,
                cache=cast(SignatureRetryCache, cache),
                index=0,
            )
    return RetryCacheState(
        workflow_id=workflow_id,
        is_retry=False,
        cache=None,
        index=0,
    )


async def teardown_retry_cache(state: RetryCacheState):
    try:
        if state.cache:
            await state.cache.adelete()
    except Exception:
        pass


async def get_cached_signature(
    state: RetryCacheState, sig_type: Type[T]
) -> Optional[T]:
    cache = state.cache
    if cache is None or state.index >= len(cache.signature_ids):
        return None
    sig_key = cache.signature_ids[state.index]
    state.index += 1
    try:
        sig = await rapyer.afind_one(sig_key)
    except Exception:
        return None
    if sig is None:
        return None
    return cast(T, sig)


async def cache_signature(state: RetryCacheState, signature: Signature):
    if state.cache is None:
        state.cache = SignatureRetryCache(workflow_id=state.workflow_id)
        state.cache.pk = state.workflow_id
        await state.cache.asave()
    state.cache.signature_ids.append(signature.key)
    await state.cache.asave()
    state.index += 1
