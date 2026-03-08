import pytest
import rapyer

import thirdmagic
from tests.unit.utils import extract_hatchet_validator
from thirdmagic.chain.creator import chain
from thirdmagic.signature.retry_cache import (
    RetryCacheState,
    SignatureRetryCache,
    cache_signature,
    get_cached_signature,
    retry_cache_ctx,
    setup_retry_cache,
    teardown_retry_cache,
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
    # Arrange
    expected_cache = SignatureRetryCache(workflow_id="wf-123")

    # Act
    state = await setup_retry_cache("wf-123", attempt_number=1)

    # Assert
    assert state.workflow_id == "wf-123"
    assert state.is_retry is False
    assert state.cache == expected_cache
    assert state.index == 0


@pytest.mark.asyncio
async def test__setup_retry_cache__retry_no_cache_in_redis__returns_retry():
    # Arrange
    cache = SignatureRetryCache(workflow_id="wf-no-cache")

    # Act
    state = await setup_retry_cache("wf-no-cache", attempt_number=2)

    # Assert
    assert state.is_retry is True
    assert state.cache == cache


@pytest.mark.asyncio
async def test__setup_retry_cache__retry_with_cache_in_redis__returns_retry_with_cache():
    # Arrange
    cache = SignatureRetryCache(workflow_id="wf-cached")
    cache.pk = "wf-cached"
    await cache.asave()

    # Act
    state = await setup_retry_cache("wf-cached", attempt_number=2)

    # Assert
    assert state.is_retry is True
    assert state.cache is not None
    assert state.cache.workflow_id == "wf-cached"


# --- cache_signature / get_cached_signature round-trip ---


@pytest.mark.asyncio
async def test__cache_and_get__round_trip__returns_same_signature(hatchet_mock):
    # Arrange
    @hatchet_mock.task(name="test_task")
    def test_task(msg):
        return msg

    sig = await TaskSignature.from_task(test_task)
    state = await setup_retry_cache("wf-rt", attempt_number=1)
    token = retry_cache_ctx.set(state)

    # Act - cache it
    try:
        await cache_signature(sig)
    finally:
        retry_cache_ctx.reset(token)

    # Assert - cache populated
    assert state.cache is not None
    assert len(state.cache.signature_ids) == 1
    assert state.index == 1

    # Act - retrieve it
    retrieval_state = await setup_retry_cache("wf-rt", attempt_number=2)
    token2 = retry_cache_ctx.set(retrieval_state)
    try:
        cached_sig = await get_cached_signature(TaskSignature)
    finally:
        retry_cache_ctx.reset(token2)

    # Assert - same signature returned
    assert retrieval_state.is_retry is True
    assert cached_sig is not None
    assert cached_sig.key == sig.key


@pytest.mark.asyncio
async def test__get_cached_signature__index_out_of_range__returns_none():
    # Arrange
    cache = SignatureRetryCache(workflow_id="wf-empty")
    cache.pk = "wf-empty"
    await cache.asave()
    state = RetryCacheState(workflow_id="wf-empty", is_retry=True, cache=cache, index=0)
    token = retry_cache_ctx.set(state)

    # Act
    try:
        result = await get_cached_signature(TaskSignature)
    finally:
        retry_cache_ctx.reset(token)

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test__get_cached_signature__signature_deleted__returns_none(hatchet_mock):
    # Arrange
    @hatchet_mock.task(name="test_task")
    def test_task(msg):
        return msg

    sig = await TaskSignature.from_task(test_task)
    state = await setup_retry_cache("wf-del", attempt_number=1)
    token = retry_cache_ctx.set(state)
    try:
        await cache_signature(sig)
    finally:
        retry_cache_ctx.reset(token)
    await sig.adelete()

    # Act
    retrieval_state = await setup_retry_cache("wf-del", attempt_number=2)
    token2 = retry_cache_ctx.set(retrieval_state)
    try:
        cached_sig = await get_cached_signature(TaskSignature)
    finally:
        retry_cache_ctx.reset(token2)

    # Assert
    assert cached_sig is None


# --- teardown_retry_cache ---


@pytest.mark.asyncio
async def test__teardown__deletes_cache_from_redis(redis_client):
    # Arrange
    cache = SignatureRetryCache(workflow_id="wf-td")
    cache.pk = "wf-td"
    await cache.asave()
    state = RetryCacheState(workflow_id="wf-td", is_retry=False, cache=cache)

    # Act
    await teardown_retry_cache(state)

    # Assert
    assert not await redis_client.exists(cache.key)


# --- sign() integration with cache ---


@pytest.mark.asyncio
async def test__sign__first_attempt__caches_signature(hatchet_mock):
    # Arrange
    @hatchet_mock.task(name="cached_task")
    def cached_task(msg):
        return msg

    state = await setup_retry_cache("wf-sign-1", attempt_number=1)
    token = retry_cache_ctx.set(state)

    # Act
    try:
        sig = await thirdmagic.sign(cached_task)
    finally:
        retry_cache_ctx.reset(token)

    # Assert
    assert state.cache is not None
    assert len(state.cache.signature_ids) == 1
    assert state.cache.signature_ids[0] == sig.key


@pytest.mark.asyncio
async def test__sign__retry__returns_cached_signature(hatchet_mock):
    # Arrange
    @hatchet_mock.task(name="cached_task")
    def cached_task(msg):
        return msg

    state1 = await setup_retry_cache("wf-sign-2", attempt_number=1)
    token1 = retry_cache_ctx.set(state1)
    try:
        original_sig = await thirdmagic.sign(cached_task)
    finally:
        retry_cache_ctx.reset(token1)

    # Act
    state2 = await setup_retry_cache("wf-sign-2", attempt_number=2)
    token2 = retry_cache_ctx.set(state2)
    try:
        cached_sig = await thirdmagic.sign(cached_task)
    finally:
        retry_cache_ctx.reset(token2)

    # Assert
    assert cached_sig.key == original_sig.key


@pytest.mark.asyncio
async def test__sign__retry_more_signatures_than_cached__creates_new(hatchet_mock):
    # Arrange
    @hatchet_mock.task(name="task_a")
    def task_a(msg):
        return msg

    @hatchet_mock.task(name="task_b")
    def task_b(msg):
        return msg

    state1 = await setup_retry_cache("wf-sign-3", attempt_number=1)
    token1 = retry_cache_ctx.set(state1)
    try:
        sig_a = await thirdmagic.sign(task_a)
    finally:
        retry_cache_ctx.reset(token1)

    # Act
    state2 = await setup_retry_cache("wf-sign-3", attempt_number=2)
    token2 = retry_cache_ctx.set(state2)
    try:
        cached_a = await thirdmagic.sign(task_a)
        new_b = await thirdmagic.sign(task_b)
    finally:
        retry_cache_ctx.reset(token2)

    # Assert
    assert cached_a.key == sig_a.key
    assert new_b.key != sig_a.key


# --- chain() integration with cache ---


@pytest.mark.asyncio
async def test__chain__first_attempt__caches_chain_signature(hatchet_mock):
    # Arrange
    @hatchet_mock.task(name="chain_task_1")
    def chain_task_1(msg):
        return msg

    @hatchet_mock.task(name="chain_task_2")
    def chain_task_2(msg):
        return msg

    state = await setup_retry_cache("wf-chain-1", attempt_number=1)
    token = retry_cache_ctx.set(state)

    # Act
    try:
        chain_sig = await chain([chain_task_1, chain_task_2])
    finally:
        retry_cache_ctx.reset(token)

    # Assert
    assert state.cache is not None
    assert len(state.cache.signature_ids) == 1
    assert state.cache.signature_ids[0] == chain_sig.key


@pytest.mark.asyncio
async def test__chain__retry__returns_cached_chain(hatchet_mock):
    # Arrange
    @hatchet_mock.task(name="chain_task_1")
    def chain_task_1(msg):
        return msg

    @hatchet_mock.task(name="chain_task_2")
    def chain_task_2(msg):
        return msg

    state1 = await setup_retry_cache("wf-chain-2", attempt_number=1)
    token1 = retry_cache_ctx.set(state1)
    try:
        original_chain = await chain([chain_task_1, chain_task_2])
    finally:
        retry_cache_ctx.reset(token1)

    # Act
    state2 = await setup_retry_cache("wf-chain-2", attempt_number=2)
    token2 = retry_cache_ctx.set(state2)
    try:
        cached_chain = await chain([chain_task_1, chain_task_2])
    finally:
        retry_cache_ctx.reset(token2)

    # Assert
    assert cached_chain.key == original_chain.key


# --- swarm() integration with cache ---


@pytest.mark.asyncio
async def test__swarm__first_attempt__caches_swarm_signature(hatchet_mock):
    # Arrange
    @hatchet_mock.task(name="swarm_task")
    def swarm_task(msg):
        return msg

    state = await setup_retry_cache("wf-swarm-1", attempt_number=1)
    token = retry_cache_ctx.set(state)

    # Act
    try:
        swarm_sig = await swarm([swarm_task], task_name="test-swarm")
    finally:
        retry_cache_ctx.reset(token)

    # Assert
    assert state.cache is not None
    assert len(state.cache.signature_ids) == 1
    assert state.cache.signature_ids[0] == swarm_sig.key


@pytest.mark.asyncio
async def test__swarm__retry__returns_cached_swarm(hatchet_mock):
    # Arrange
    @hatchet_mock.task(name="swarm_task")
    def swarm_task(msg):
        return msg

    state1 = await setup_retry_cache("wf-swarm-2", attempt_number=1)
    token1 = retry_cache_ctx.set(state1)
    try:
        original_swarm = await swarm([swarm_task], task_name="test-swarm")
    finally:
        retry_cache_ctx.reset(token1)

    # Act
    state2 = await setup_retry_cache("wf-swarm-2", attempt_number=2)
    token2 = retry_cache_ctx.set(state2)
    try:
        cached_swarm = await swarm([swarm_task], task_name="test-swarm")
    finally:
        retry_cache_ctx.reset(token2)

    # Assert
    assert cached_swarm.key == original_swarm.key


# --- No context (normal usage outside tasks) ---


@pytest.mark.asyncio
async def test__sign__no_cache_context__creates_normally(hatchet_mock):
    # Arrange
    @hatchet_mock.task(name="normal_task")
    def normal_task(msg):
        return msg

    # Act
    sig = await thirdmagic.sign(normal_task)

    # Assert
    assert sig is not None
    assert sig.task_name == "normal_task"


# --- Multiple signatures in sequence ---


@pytest.mark.asyncio
async def test__sign__multiple_signatures__all_cached_and_restored(hatchet_mock):
    # Arrange
    @hatchet_mock.task(name="task_1")
    def task_1(msg):
        return msg

    @hatchet_mock.task(name="task_2")
    def task_2(msg):
        return msg

    @hatchet_mock.task(name="task_3")
    def task_3(msg):
        return msg

    state1 = await setup_retry_cache("wf-multi", attempt_number=1)
    token1 = retry_cache_ctx.set(state1)
    try:
        sig1 = await thirdmagic.sign(task_1)
        sig2 = await thirdmagic.sign(task_2)
        sig3 = await thirdmagic.sign(task_3)
    finally:
        retry_cache_ctx.reset(token1)

    assert len(state1.cache.signature_ids) == 3

    # Act
    state2 = await setup_retry_cache("wf-multi", attempt_number=2)
    token2 = retry_cache_ctx.set(state2)
    try:
        cached1 = await thirdmagic.sign(task_1)
        cached2 = await thirdmagic.sign(task_2)
        cached3 = await thirdmagic.sign(task_3)
    finally:
        retry_cache_ctx.reset(token2)

    # Assert
    assert cached1.key == sig1.key
    assert cached2.key == sig2.key
    assert cached3.key == sig3.key


# --- Mixed signature types in pipeline ---


@pytest.mark.asyncio
async def test__abounded_field__mixed_signatures__all_cached_in_order(hatchet_mock):
    # Arrange
    @hatchet_mock.task(name="task_a")
    def task_a(msg):
        return msg

    @hatchet_mock.task(name="swarm_task")
    def swarm_task(msg):
        return msg

    @hatchet_mock.task(name="chain_task_1")
    def chain_task_1(msg):
        return msg

    @hatchet_mock.task(name="chain_task_2")
    def chain_task_2(msg):
        return msg

    # Act - first attempt: create mixed signatures inside a pipeline
    state1 = await setup_retry_cache("wf-mixed", attempt_number=1)
    token1 = retry_cache_ctx.set(state1)
    try:
        async with rapyer.apipeline():
            sig_a = await thirdmagic.sign(task_a)
            swarm_sig = await swarm([swarm_task], task_name="test-swarm")
            chain_sig = await chain([chain_task_1, chain_task_2])
    finally:
        retry_cache_ctx.reset(token1)

    # Assert - all three cached in order
    assert len(state1.cache.signature_ids) == 3
    assert state1.cache.signature_ids[0] == sig_a.key
    assert state1.cache.signature_ids[1] == swarm_sig.key
    assert state1.cache.signature_ids[2] == chain_sig.key

    # Act - retry: same calls should return cached signatures
    state2 = await setup_retry_cache("wf-mixed", attempt_number=2)
    token2 = retry_cache_ctx.set(state2)
    try:
        async with rapyer.apipeline():
            cached_a = await thirdmagic.sign(task_a)
            cached_swarm = await swarm([swarm_task], task_name="test-swarm")
            cached_chain = await chain([chain_task_1, chain_task_2])
    finally:
        retry_cache_ctx.reset(token2)

    # Assert - each returns the original cached signature
    assert cached_a.key == sig_a.key
    assert cached_swarm.key == swarm_sig.key
    assert cached_chain.key == chain_sig.key


# --- Crash mid-pipeline leaves cache unchanged ---


@pytest.mark.asyncio
async def test__abounded_field__crash_mid_pipeline__cache_unchanged(hatchet_mock):
    # Arrange
    @hatchet_mock.task(name="task_pre")
    def task_pre(msg):
        return msg

    @hatchet_mock.task(name="task_crash")
    def task_crash(msg):
        return msg

    # Act - first attempt: create one signature outside any extra pipeline
    state = await setup_retry_cache("wf-crash", attempt_number=1)
    token = retry_cache_ctx.set(state)
    try:
        pre_sig = await thirdmagic.sign(task_pre)
    finally:
        retry_cache_ctx.reset(token)

    assert len(state.cache.signature_ids) == 1

    # Act - start a pipeline, create another signature, then crash
    token2 = retry_cache_ctx.set(state)
    try:
        with pytest.raises(RuntimeError):
            async with rapyer.apipeline():
                await thirdmagic.sign(task_crash)
                raise RuntimeError("simulated crash")
    finally:
        retry_cache_ctx.reset(token2)

    # Assert - reload cache from Redis; should still have only 1 entry
    reloaded_cache = await SignatureRetryCache.afind_one("wf-crash")
    assert reloaded_cache is not None
    assert len(reloaded_cache.signature_ids) == 1
    assert reloaded_cache.signature_ids[0] == pre_sig.key

    # Verify the pre-crash signature is still retrievable on retry
    state3 = await setup_retry_cache("wf-crash", attempt_number=2)
    token3 = retry_cache_ctx.set(state3)
    try:
        retrieved = await thirdmagic.sign(task_pre)
    finally:
        retry_cache_ctx.reset(token3)

    assert retrieved.key == pre_sig.key
