import pytest
import pytest_asyncio
import rapyer

import thirdmagic
from tests.unit.utils import extract_hatchet_validator
from thirdmagic.chain.creator import chain
from thirdmagic.signature.retry_cache import (
    SignatureRetryCache,
    RetryCacheState,
    retry_cache_ctx,
    setup_retry_cache,
    teardown_retry_cache,
    get_cached_signature,
    cache_signature,
)
from thirdmagic.swarm.creator import swarm
from thirdmagic.task.model import TaskSignature


@pytest.fixture(autouse=True)
def client_adapter(mock_adapter):
    mock_adapter.extract_validator.side_effect = extract_hatchet_validator
    mock_adapter.task_name.side_effect = lambda fn: fn.name
    yield mock_adapter


# --- setup_retry_cache ---


@pytest.mark.asyncio
async def test__setup_retry_cache__first_attempt__returns_not_retry():
    state = await setup_retry_cache("wf-123", attempt_number=1)
    assert state.workflow_id == "wf-123"
    assert state.is_retry is False
    assert state.cache is None
    assert state.index == 0


@pytest.mark.asyncio
async def test__setup_retry_cache__retry_no_cache_in_redis__returns_not_retry():
    state = await setup_retry_cache("wf-no-cache", attempt_number=2)
    assert state.is_retry is False
    assert state.cache is None


@pytest.mark.asyncio
async def test__setup_retry_cache__retry_with_cache_in_redis__returns_retry_with_cache():
    # Pre-populate cache in Redis
    cache = SignatureRetryCache(workflow_id="wf-cached")
    cache.pk = "wf-cached"
    await cache.asave()

    state = await setup_retry_cache("wf-cached", attempt_number=2)
    assert state.is_retry is True
    assert state.cache is not None
    assert state.cache.workflow_id == "wf-cached"


# --- cache_signature / get_cached_signature round-trip ---


@pytest.mark.asyncio
async def test__cache_and_get__round_trip__returns_same_signature(hatchet_mock):
    @hatchet_mock.task(name="test_task")
    def test_task(msg):
        return msg

    sig = await TaskSignature.from_task(test_task)

    # Cache it
    state = RetryCacheState(workflow_id="wf-rt", is_retry=False)
    await cache_signature(state, sig)
    assert state.cache is not None
    assert len(state.cache.signature_ids) == 1
    assert state.index == 1

    # Retrieve it
    retrieval_state = await setup_retry_cache("wf-rt", attempt_number=2)
    assert retrieval_state.is_retry is True
    cached_sig = await get_cached_signature(retrieval_state, TaskSignature)
    assert cached_sig is not None
    assert cached_sig.key == sig.key


@pytest.mark.asyncio
async def test__get_cached_signature__index_out_of_range__returns_none():
    cache = SignatureRetryCache(workflow_id="wf-empty")
    cache.pk = "wf-empty"
    await cache.asave()

    state = RetryCacheState(
        workflow_id="wf-empty", is_retry=True, cache=cache, index=0
    )
    result = await get_cached_signature(state, TaskSignature)
    assert result is None


@pytest.mark.asyncio
async def test__get_cached_signature__signature_deleted__returns_none(hatchet_mock):
    @hatchet_mock.task(name="test_task")
    def test_task(msg):
        return msg

    sig = await TaskSignature.from_task(test_task)

    state = RetryCacheState(workflow_id="wf-del", is_retry=False)
    await cache_signature(state, sig)

    # Delete the signature from Redis
    await sig.adelete()

    retrieval_state = await setup_retry_cache("wf-del", attempt_number=2)
    cached_sig = await get_cached_signature(retrieval_state, TaskSignature)
    assert cached_sig is None


# --- teardown_retry_cache ---


@pytest.mark.asyncio
async def test__teardown__deletes_cache_from_redis(redis_client):
    cache = SignatureRetryCache(workflow_id="wf-td")
    cache.pk = "wf-td"
    await cache.asave()

    state = RetryCacheState(
        workflow_id="wf-td", is_retry=False, cache=cache
    )
    await teardown_retry_cache(state)

    assert not await redis_client.exists(cache.key)


@pytest.mark.asyncio
async def test__teardown__no_cache__does_not_raise():
    state = RetryCacheState(workflow_id="wf-none", is_retry=False, cache=None)
    await teardown_retry_cache(state)  # should not raise


# --- sign() integration with cache ---


@pytest.mark.asyncio
async def test__sign__first_attempt__caches_signature(hatchet_mock):
    @hatchet_mock.task(name="cached_task")
    def cached_task(msg):
        return msg

    state = await setup_retry_cache("wf-sign-1", attempt_number=1)
    token = retry_cache_ctx.set(state)
    try:
        sig = await thirdmagic.sign(cached_task)
        assert state.cache is not None
        assert len(state.cache.signature_ids) == 1
        assert state.cache.signature_ids[0] == sig.key
    finally:
        retry_cache_ctx.reset(token)


@pytest.mark.asyncio
async def test__sign__retry__returns_cached_signature(hatchet_mock):
    @hatchet_mock.task(name="cached_task")
    def cached_task(msg):
        return msg

    # First attempt: create and cache
    state1 = await setup_retry_cache("wf-sign-2", attempt_number=1)
    token1 = retry_cache_ctx.set(state1)
    try:
        original_sig = await thirdmagic.sign(cached_task)
    finally:
        retry_cache_ctx.reset(token1)

    # Retry: should return cached signature
    state2 = await setup_retry_cache("wf-sign-2", attempt_number=2)
    token2 = retry_cache_ctx.set(state2)
    try:
        cached_sig = await thirdmagic.sign(cached_task)
        assert cached_sig.key == original_sig.key
    finally:
        retry_cache_ctx.reset(token2)


@pytest.mark.asyncio
async def test__sign__retry_more_signatures_than_cached__creates_new(hatchet_mock):
    @hatchet_mock.task(name="task_a")
    def task_a(msg):
        return msg

    @hatchet_mock.task(name="task_b")
    def task_b(msg):
        return msg

    # First attempt: cache only one signature
    state1 = await setup_retry_cache("wf-sign-3", attempt_number=1)
    token1 = retry_cache_ctx.set(state1)
    try:
        sig_a = await thirdmagic.sign(task_a)
    finally:
        retry_cache_ctx.reset(token1)

    # Retry: first sign returns cached, second creates new
    state2 = await setup_retry_cache("wf-sign-3", attempt_number=2)
    token2 = retry_cache_ctx.set(state2)
    try:
        cached_a = await thirdmagic.sign(task_a)
        assert cached_a.key == sig_a.key

        new_b = await thirdmagic.sign(task_b)
        assert new_b.key != sig_a.key
    finally:
        retry_cache_ctx.reset(token2)


# --- chain() integration with cache ---


@pytest.mark.asyncio
async def test__chain__first_attempt__caches_chain_signature(hatchet_mock):
    @hatchet_mock.task(name="chain_task_1")
    def chain_task_1(msg):
        return msg

    @hatchet_mock.task(name="chain_task_2")
    def chain_task_2(msg):
        return msg

    state = await setup_retry_cache("wf-chain-1", attempt_number=1)
    token = retry_cache_ctx.set(state)
    try:
        chain_sig = await chain([chain_task_1, chain_task_2])
        assert state.cache is not None
        assert len(state.cache.signature_ids) == 1
        assert state.cache.signature_ids[0] == chain_sig.key
    finally:
        retry_cache_ctx.reset(token)


@pytest.mark.asyncio
async def test__chain__retry__returns_cached_chain(hatchet_mock):
    @hatchet_mock.task(name="chain_task_1")
    def chain_task_1(msg):
        return msg

    @hatchet_mock.task(name="chain_task_2")
    def chain_task_2(msg):
        return msg

    # First attempt
    state1 = await setup_retry_cache("wf-chain-2", attempt_number=1)
    token1 = retry_cache_ctx.set(state1)
    try:
        original_chain = await chain([chain_task_1, chain_task_2])
    finally:
        retry_cache_ctx.reset(token1)

    # Retry
    state2 = await setup_retry_cache("wf-chain-2", attempt_number=2)
    token2 = retry_cache_ctx.set(state2)
    try:
        cached_chain = await chain([chain_task_1, chain_task_2])
        assert cached_chain.key == original_chain.key
    finally:
        retry_cache_ctx.reset(token2)


# --- swarm() integration with cache ---


@pytest.mark.asyncio
async def test__swarm__first_attempt__caches_swarm_signature(hatchet_mock):
    @hatchet_mock.task(name="swarm_task")
    def swarm_task(msg):
        return msg

    state = await setup_retry_cache("wf-swarm-1", attempt_number=1)
    token = retry_cache_ctx.set(state)
    try:
        swarm_sig = await swarm([swarm_task], task_name="test-swarm")
        assert state.cache is not None
        assert len(state.cache.signature_ids) == 1
        assert state.cache.signature_ids[0] == swarm_sig.key
    finally:
        retry_cache_ctx.reset(token)


@pytest.mark.asyncio
async def test__swarm__retry__returns_cached_swarm(hatchet_mock):
    @hatchet_mock.task(name="swarm_task")
    def swarm_task(msg):
        return msg

    # First attempt
    state1 = await setup_retry_cache("wf-swarm-2", attempt_number=1)
    token1 = retry_cache_ctx.set(state1)
    try:
        original_swarm = await swarm([swarm_task], task_name="test-swarm")
    finally:
        retry_cache_ctx.reset(token1)

    # Retry
    state2 = await setup_retry_cache("wf-swarm-2", attempt_number=2)
    token2 = retry_cache_ctx.set(state2)
    try:
        cached_swarm = await swarm([swarm_task], task_name="test-swarm")
        assert cached_swarm.key == original_swarm.key
    finally:
        retry_cache_ctx.reset(token2)


# --- No context (normal usage outside tasks) ---


@pytest.mark.asyncio
async def test__sign__no_cache_context__creates_normally(hatchet_mock):
    @hatchet_mock.task(name="normal_task")
    def normal_task(msg):
        return msg

    # No contextvar set — should work as before
    sig = await thirdmagic.sign(normal_task)
    assert sig is not None
    assert sig.task_name == "normal_task"


# --- Multiple signatures in sequence ---


@pytest.mark.asyncio
async def test__sign__multiple_signatures__all_cached_and_restored(hatchet_mock):
    @hatchet_mock.task(name="task_1")
    def task_1(msg):
        return msg

    @hatchet_mock.task(name="task_2")
    def task_2(msg):
        return msg

    @hatchet_mock.task(name="task_3")
    def task_3(msg):
        return msg

    # First attempt: create 3 signatures
    state1 = await setup_retry_cache("wf-multi", attempt_number=1)
    token1 = retry_cache_ctx.set(state1)
    try:
        sig1 = await thirdmagic.sign(task_1)
        sig2 = await thirdmagic.sign(task_2)
        sig3 = await thirdmagic.sign(task_3)
    finally:
        retry_cache_ctx.reset(token1)

    assert len(state1.cache.signature_ids) == 3

    # Retry: all 3 should come from cache in order
    state2 = await setup_retry_cache("wf-multi", attempt_number=2)
    token2 = retry_cache_ctx.set(state2)
    try:
        cached1 = await thirdmagic.sign(task_1)
        cached2 = await thirdmagic.sign(task_2)
        cached3 = await thirdmagic.sign(task_3)
        assert cached1.key == sig1.key
        assert cached2.key == sig2.key
        assert cached3.key == sig3.key
    finally:
        retry_cache_ctx.reset(token2)
