import asyncio
from unittest.mock import AsyncMock, patch

import pytest
import rapyer
import thirdmagic
from thirdmagic.signature.retry_cache import (
    SignatureRetryCache,
    retry_cache_ctx,
)
from thirdmagic.task import TaskSignature

from mageflow.callbacks import handle_task_callback
from tests.integration.hatchet.models import ContextMessage
from tests.unit.callbacks.conftest import (
    MockContextConfig,
    create_mock_hatchet_context,
    handler_factory,
    task_signature_factory,
)


@pytest.fixture(autouse=True)
def _restore_retry_cache_ctx():
    token = retry_cache_ctx.set(None)
    yield
    retry_cache_ctx.reset(token)


# --- Durable task: cache is created on first attempt ---


@pytest.mark.asyncio
async def test__durable_task__first_attempt__cache_created(
    adapter_with_lifecycle,
    redis_client,
):
    # Arrange
    signature, _ = await task_signature_factory()
    workflow_id = "wf-cache-created"
    ctx = create_mock_hatchet_context(
        MockContextConfig(
            task_id=signature.key,
            job_name="test_task",
            attempt_number=1,
            workflow_id=workflow_id,
        )
    )

    async def user_func(msg):
        task_model = await thirdmagic.sign("test_task", model_validators=ContextMessage)
        return task_model.key

    handler = handle_task_callback(is_idempotent=True)(user_func)
    message = ContextMessage()

    # Act
    result = await handler(message, ctx)

    # Assert - cache should exist in Redis with the created signature
    cache_key = f"SignatureRetryCache:{workflow_id}"
    # Cache is torn down on success, so it should NOT exist after success
    assert not await redis_client.exists(cache_key)


@pytest.mark.asyncio
async def test__durable_task__first_attempt_error_with_retry__cache_persists(
    adapter_with_lifecycle,
    redis_client,
):
    # Arrange
    signature, _ = await task_signature_factory(retries=3)
    workflow_id = "wf-cache-persists"
    ctx = create_mock_hatchet_context(
        MockContextConfig(
            task_id=signature.key,
            job_name="test_task",
            attempt_number=1,
            workflow_id=workflow_id,
        )
    )

    created_sig_key = None

    async def user_func(msg):
        nonlocal created_sig_key

        sig = await thirdmagic.sign("test_task", model_validators=ContextMessage)
        created_sig_key = sig.key
        raise ValueError("Retryable error")

    from mageflow.callbacks import handle_task_callback

    handler = handle_task_callback(is_idempotent=True)(user_func)
    message = ContextMessage()

    # Act
    with pytest.raises(ValueError, match="Retryable error"):
        await handler(message, ctx)

    # Verify the cache contains the created signature
    cache = await SignatureRetryCache.aget(workflow_id)
    assert len(cache.signature_ids) == 1
    assert cache.signature_ids[0] == created_sig_key


@pytest.mark.asyncio
async def test__durable_task__retry_attempt__returns_cached_signature(
    adapter_with_lifecycle,
    redis_client,
):
    # Arrange - simulate first attempt that cached a signature
    workflow_id = "wf-retry-returns-cached"

    # Create the signature that would have been created on first attempt
    original_sig = await TaskSignature.from_task_name(
        "test_task", model_validators=ContextMessage
    )

    # Pre-populate cache
    cache = SignatureRetryCache(workflow_id=workflow_id)
    cache.pk = workflow_id
    cache.signature_ids.append(original_sig.key)
    await cache.asave()

    # Create the task signature for the handler lifecycle
    signature, _ = await task_signature_factory()
    ctx = create_mock_hatchet_context(
        MockContextConfig(
            task_id=signature.key,
            job_name="test_task",
            attempt_number=2,
            workflow_id=workflow_id,
        )
    )

    created_sig_key = None

    async def user_func(msg):
        nonlocal created_sig_key

        sig = await thirdmagic.sign("test_task", model_validators=ContextMessage)
        created_sig_key = sig.key
        return "success"

    handler = handle_task_callback(is_idempotent=True)(user_func)
    message = ContextMessage()

    # Act
    result = await handler(message, ctx)

    # Assert - the signature created in user func should be the cached one
    assert created_sig_key == original_sig.key


@pytest.mark.asyncio
async def test__durable_task__success__cache_deleted(
    adapter_with_lifecycle,
    redis_client,
):
    # Arrange
    signature, _ = await task_signature_factory()
    workflow_id = "wf-success-cleanup"
    ctx = create_mock_hatchet_context(
        MockContextConfig(
            task_id=signature.key,
            job_name="test_task",
            attempt_number=1,
            workflow_id=workflow_id,
        )
    )

    async def user_func(msg):
        await thirdmagic.sign("test_task", model_validators=ContextMessage)
        return "done"

    handler = handle_task_callback(is_idempotent=True)(user_func)
    message = ContextMessage()

    # Act
    await handler(message, ctx)

    # Assert - cache should be cleaned up after success
    cache_key = f"SignatureRetryCache:{workflow_id}"
    assert not await redis_client.exists(cache_key)


@pytest.mark.asyncio
async def test__durable_task__cancel_error_not_yet_finished__cache_not_deleted(
    adapter_with_lifecycle,
    redis_client,
):
    # Arrange
    signature, _ = await task_signature_factory(retries=3)
    workflow_id = "wf-cancel-cleanup"
    ctx = create_mock_hatchet_context(
        MockContextConfig(
            task_id=signature.key,
            job_name="test_task",
            attempt_number=4,
            workflow_id=workflow_id,
        )
    )
    adapter_with_lifecycle.should_task_retry.return_value = True

    async def user_func(msg):
        await thirdmagic.sign("test_task", model_validators=ContextMessage)
        raise asyncio.CancelledError()

    handler = handle_task_callback(is_idempotent=True)(user_func)
    message = ContextMessage()

    # Act - CancelledError should propagate
    with pytest.raises(asyncio.CancelledError):
        await handler(message, ctx)

    # Assert - cache should be deleted even though retries are configured
    cache_key = f"SignatureRetryCache:{workflow_id}"
    assert await redis_client.exists(cache_key)


@pytest.mark.asyncio
async def test__durable_task__cancel_error_with_delete_failure__raises_cancel_error(
    adapter_with_lifecycle,
    redis_client,
):
    # Arrange
    signature, _ = await task_signature_factory(retries=1)
    workflow_id = "wf-cancel-delete-fail"
    ctx = create_mock_hatchet_context(
        MockContextConfig(
            task_id=signature.key,
            job_name="test_task",
            attempt_number=2,
            workflow_id=workflow_id,
        )
    )
    adapter_with_lifecycle.should_task_retry.return_value = False

    async def user_func(msg):
        await thirdmagic.sign("test_task", model_validators=ContextMessage)
        raise asyncio.CancelledError()

    handler = handle_task_callback(is_idempotent=True)(user_func)
    message = ContextMessage()

    # Act - CancelledError should propagate even when cache.adelete() fails
    with patch.object(
        SignatureRetryCache,
        "adelete",
        new_callable=AsyncMock,
        side_effect=ConnectionError("Redis unavailable"),
    ) as mock_adelete:
        with pytest.raises(asyncio.CancelledError):
            await handler(message, ctx)
        mock_adelete.assert_awaited_once()


# --- Non-durable task: cache is NOT created ---


@pytest.mark.asyncio
async def test__non_durable_task__no_cache_created(
    adapter_with_lifecycle,
    redis_client,
):
    # Arrange
    signature, _ = await task_signature_factory()
    workflow_id = "wf-no-cache"
    ctx = create_mock_hatchet_context(
        MockContextConfig(
            task_id=signature.key,
            job_name="test_task",
            attempt_number=1,
            workflow_id=workflow_id,
        )
    )

    async def user_func(msg):
        await thirdmagic.sign("test_task", model_validators=ContextMessage)
        return "done"

    handler = handle_task_callback()(user_func)
    message = ContextMessage()

    # Act
    await handler(message, ctx)

    # Assert - no cache should exist for non-durable tasks
    cache_key = f"SignatureRetryCache:{workflow_id}"
    assert not await redis_client.exists(cache_key)


@pytest.mark.asyncio
async def test__non_durable_task__retry_creates_new_signatures(
    adapter_with_lifecycle,
    redis_client,
):
    # Arrange - pre-populate cache (shouldn't be used by non-durable)
    workflow_id = "wf-non-durable-retry"
    original_sig = await TaskSignature.from_task_name(
        "test_task", model_validators=ContextMessage
    )
    cache = SignatureRetryCache(workflow_id=workflow_id)
    cache.pk = workflow_id
    cache.signature_ids.append(original_sig.key)
    await cache.asave()

    signature, _ = await task_signature_factory(retries=3)
    ctx = create_mock_hatchet_context(
        MockContextConfig(
            task_id=signature.key,
            job_name="test_task",
            attempt_number=2,
            workflow_id=workflow_id,
        )
    )

    created_sig_key = None

    async def user_func(msg):
        nonlocal created_sig_key

        sig = await thirdmagic.sign("test_task", model_validators=ContextMessage)
        created_sig_key = sig.key
        return "done"

    handler = handle_task_callback()(user_func)
    message = ContextMessage()

    # Act
    await handler(message, ctx)

    # Assert - non-durable task creates NEW signature, not cached one
    assert created_sig_key != original_sig.key


# --- Vanilla task (task_id=None) error scenarios ---


@pytest.mark.asyncio
async def test__vanilla_task__error_no_retry__cache_deleted(
    adapter_with_lifecycle,
    redis_client,
):
    # Arrange - no retries, so should_task_retry returns False
    await task_signature_factory(retries=0)
    workflow_id = "wf-vanilla-error-no-retry"
    adapter_with_lifecycle.should_task_retry.return_value = False
    ctx = create_mock_hatchet_context(
        MockContextConfig(
            task_id=None,
            job_name="test_task",
            workflow_id=workflow_id,
        )
    )

    async def user_func(msg):
        await thirdmagic.sign("test_task", model_validators=ContextMessage)
        raise ValueError("Fatal error")

    handler = handle_task_callback(is_idempotent=True)(user_func)
    message = ContextMessage()

    # Act
    with pytest.raises(ValueError, match="Fatal error"):
        await handler(message, ctx)

    # Assert - cache should be deleted since no retry will happen
    cache_key = f"SignatureRetryCache:{workflow_id}"
    assert not await redis_client.exists(cache_key)


@pytest.mark.asyncio
async def test__vanilla_task__cancel_error_with_retries__cache_not_deleted(
    adapter_with_lifecycle,
    redis_client,
):
    # Arrange
    await task_signature_factory(retries=3)
    workflow_id = "wf-vanilla-cancel"
    ctx = create_mock_hatchet_context(
        MockContextConfig(
            task_id=None,
            job_name="test_task",
            workflow_id=workflow_id,
        )
    )

    async def user_func(msg):
        await thirdmagic.sign("test_task", model_validators=ContextMessage)
        raise asyncio.CancelledError()

    handler = handle_task_callback(is_idempotent=True)(user_func)
    message = ContextMessage()

    # Act - CancelledError should propagate
    with pytest.raises(asyncio.CancelledError):
        await handler(message, ctx)

    # Assert - cache should be deleted even though retries are configured
    cache_key = f"SignatureRetryCache:{workflow_id}"
    assert await redis_client.exists(cache_key)


@pytest.mark.asyncio
async def test__vanilla_task__error_with_retry__cache_persists(
    adapter_with_lifecycle,
    redis_client,
):
    # Arrange - retries available, so should_task_retry returns True
    await task_signature_factory(retries=3)
    workflow_id = "wf-vanilla-error-with-retry"
    adapter_with_lifecycle.should_task_retry.return_value = True
    ctx = create_mock_hatchet_context(
        MockContextConfig(
            task_id=None,
            job_name="test_task",
            attempt_number=1,
            workflow_id=workflow_id,
        )
    )

    created_sig_key = None

    async def user_func(msg):
        nonlocal created_sig_key

        sig = await thirdmagic.sign("test_task", model_validators=ContextMessage)
        created_sig_key = sig.key
        raise ValueError("Retryable error")

    handler = handle_task_callback(is_idempotent=True)(user_func)
    message = ContextMessage()

    # Act
    with pytest.raises(ValueError, match="Retryable error"):
        await handler(message, ctx)

    # Assert - cache should persist for retry
    cache = await SignatureRetryCache.aget(workflow_id)
    assert len(cache.signature_ids) == 1
    assert cache.signature_ids[0] == created_sig_key


# --- Edge case: no cache exists on retry (durable) ---


@pytest.mark.asyncio
async def test__durable_task__retry_no_cache__creates_fresh_signatures(
    adapter_with_lifecycle,
    redis_client,
):
    # Arrange - no cache in Redis
    workflow_id = "wf-no-cache-retry"
    signature, _ = await task_signature_factory(retries=3)
    ctx = create_mock_hatchet_context(
        MockContextConfig(
            task_id=signature.key,
            job_name="test_task",
            attempt_number=2,
            workflow_id=workflow_id,
        )
    )

    created_sig_key = None

    async def user_func(msg):
        nonlocal created_sig_key

        sig = await thirdmagic.sign("test_task", model_validators=ContextMessage)
        created_sig_key = sig.key
        return "done"

    handler = handle_task_callback(is_idempotent=True)(user_func)
    message = ContextMessage()

    # Act
    await handler(message, ctx)

    # Assert - a new signature was created (not from cache since cache was empty)
    assert created_sig_key is not None


# --- Edge case: vanilla task (no task_id) with durable flag ---


@pytest.mark.asyncio
async def test__durable_task__no_task_id__no_cache(
    adapter_with_lifecycle,
    redis_client,
):
    # Arrange - no task_id means vanilla run, cache should not activate
    await task_signature_factory()
    workflow_id = "wf-vanilla-durable"
    ctx = create_mock_hatchet_context(
        MockContextConfig(
            task_id=None,
            job_name="test_task",
            workflow_id=workflow_id,
        )
    )

    async def user_func(msg):
        await thirdmagic.sign("test_task", model_validators=ContextMessage)
        return "done"

    handler = handle_task_callback(is_idempotent=True)(user_func)
    message = ContextMessage()

    # Act
    result = await handler(message, ctx)

    # Assert - vanilla run returns direct result, no cache
    assert result == "done"
    cache_key = f"SignatureRetryCache:{workflow_id}"
    assert not await redis_client.exists(cache_key)


# --- Contextvar cleanup: cache context reset after handler completes ---


@pytest.mark.asyncio
async def test__durable_task__contextvar_reset_after_success(
    adapter_with_lifecycle,
):
    # Arrange
    signature, _ = await task_signature_factory()
    ctx = create_mock_hatchet_context(
        MockContextConfig(
            task_id=signature.key,
            job_name="test_task",
            workflow_id="wf-ctx-reset",
        )
    )
    returning_handler, _ = handler_factory(return_value="ok", durable=True)
    message = ContextMessage()

    # Act
    await returning_handler(message, ctx)

    # Assert - contextvar should be reset to None after handler completes
    assert retry_cache_ctx.get() is None


@pytest.mark.asyncio
async def test__durable_task__contextvar_reset_after_error(
    adapter_with_lifecycle,
):
    # Arrange
    signature, _ = await task_signature_factory(retries=3)
    ctx = create_mock_hatchet_context(
        MockContextConfig(
            task_id=signature.key,
            job_name="test_task",
            workflow_id="wf-ctx-reset-err",
        )
    )
    raising_handler, _ = handler_factory(raises=ValueError("err"), durable=True)
    message = ContextMessage()

    # Act
    with pytest.raises(ValueError):
        await raising_handler(message, ctx)

    # Assert - contextvar should be reset even after error
    assert retry_cache_ctx.get() is None


# --- Multiple signatures cached in order ---


@pytest.mark.asyncio
async def test__durable_task__multiple_signatures_cached_in_order(
    adapter_with_lifecycle,
    redis_client,
):
    # Arrange - first attempt: create multiple signatures
    workflow_id = "wf-multi-order"
    signature, _ = await task_signature_factory(retries=3)

    first_attempt_keys = []

    async def user_func_first(msg):
        sig1 = await thirdmagic.sign("test_task", model_validators=ContextMessage)
        sig2 = await thirdmagic.sign("test_task", model_validators=ContextMessage)
        sig3 = await thirdmagic.sign("test_task", model_validators=ContextMessage)
        first_attempt_keys.extend([sig1.key, sig2.key, sig3.key])
        raise ValueError("Retryable error")

    handler1 = handle_task_callback(is_idempotent=True)(user_func_first)
    ctx1 = create_mock_hatchet_context(
        MockContextConfig(
            task_id=signature.key,
            job_name="test_task",
            attempt_number=1,
            workflow_id=workflow_id,
        )
    )
    message = ContextMessage()

    with pytest.raises(ValueError):
        await handler1(message, ctx1)

    # Verify cache has 3 entries
    cache_key = f"SignatureRetryCache:{workflow_id}"
    assert await redis_client.exists(cache_key)

    # Arrange - second attempt: signatures should come from cache in order
    # Need a fresh signature for the lifecycle (original may be in wrong state)
    signature2, _ = await task_signature_factory(task_name="test_task_2", retries=3)

    retry_keys = []

    async def user_func_retry(msg):
        sig1 = await thirdmagic.sign("test_task", model_validators=ContextMessage)
        sig2 = await thirdmagic.sign("test_task", model_validators=ContextMessage)
        sig3 = await thirdmagic.sign("test_task", model_validators=ContextMessage)
        retry_keys.extend([sig1.key, sig2.key, sig3.key])
        return "success"

    handler2 = handle_task_callback(is_idempotent=True)(user_func_retry)
    ctx2 = create_mock_hatchet_context(
        MockContextConfig(
            task_id=signature2.key,
            job_name="test_task_2",
            attempt_number=2,
            workflow_id=workflow_id,
        )
    )

    # Act
    await handler2(message, ctx2)

    # Assert - same keys in same order
    assert retry_keys == first_attempt_keys


# --- Mixed signature types in pipeline cached in order ---


@pytest.mark.asyncio
async def test__durable_task__mixed_signatures_in_pipeline__all_cached_in_order(
    adapter_with_lifecycle,
    redis_client,
):
    # Arrange - first attempt: create mixed signature types inside a pipeline
    workflow_id = "wf-mixed-pipeline"
    signature, _ = await task_signature_factory(retries=3)

    first_attempt_keys = []

    async def user_func_first(msg):
        async with rapyer.apipeline():
            sig_task = await thirdmagic.sign(
                "test_task", model_validators=ContextMessage
            )
            sig_chain = await thirdmagic.chain(
                ["test_task", "test_task"], name="test-chain"
            )
            sig_swarm = await thirdmagic.swarm(["test_task"], task_name="test-swarm")
        first_attempt_keys.extend([sig_task.key, sig_chain.key, sig_swarm.key])
        raise ValueError("Retryable error")

    handler1 = handle_task_callback(is_idempotent=True)(user_func_first)
    ctx1 = create_mock_hatchet_context(
        MockContextConfig(
            task_id=signature.key,
            job_name="test_task",
            attempt_number=1,
            workflow_id=workflow_id,
        )
    )
    message = ContextMessage()

    with pytest.raises(ValueError):
        await handler1(message, ctx1)

    # Verify cache has 3 entries in correct order
    cache = await SignatureRetryCache.aget(workflow_id)
    assert len(cache.signature_ids) == 3
    assert cache.signature_ids == first_attempt_keys

    # Arrange - second attempt: signatures should come from cache in order
    signature2, _ = await task_signature_factory(task_name="test_task_2", retries=3)

    retry_keys = []

    async def user_func_retry(msg):
        async with rapyer.apipeline():
            sig_task = await thirdmagic.sign(
                "test_task", model_validators=ContextMessage
            )
            sig_chain = await thirdmagic.chain(
                ["test_task", "test_task"], name="test-chain"
            )
            sig_swarm = await thirdmagic.swarm(["test_task"], task_name="test-swarm")
        retry_keys.extend([sig_task.key, sig_chain.key, sig_swarm.key])
        return "success"

    handler2 = handle_task_callback(is_idempotent=True)(user_func_retry)
    ctx2 = create_mock_hatchet_context(
        MockContextConfig(
            task_id=signature2.key,
            job_name="test_task_2",
            attempt_number=2,
            workflow_id=workflow_id,
        )
    )

    # Act
    await handler2(message, ctx2)

    # Assert - same keys in same order
    assert retry_keys == first_attempt_keys


# --- Crash mid-pipeline leaves cache unchanged ---


@pytest.mark.asyncio
async def test__durable_task__crash_mid_pipeline__cache_unchanged(
    adapter_with_lifecycle,
    redis_client,
):
    # Arrange - first attempt: create one signature outside any extra pipeline
    workflow_id = "wf-crash-pipeline"
    signature, _ = await task_signature_factory(retries=3)

    pre_crash_key = None

    async def user_func_first(msg):
        nonlocal pre_crash_key

        pre_sig = await thirdmagic.sign("test_task", model_validators=ContextMessage)
        pre_crash_key = pre_sig.key

        # Start a pipeline, create another signature, then crash
        with pytest.raises(RuntimeError):
            async with rapyer.apipeline():
                await thirdmagic.sign("test_task", model_validators=ContextMessage)
                raise RuntimeError("simulated crash")

        raise ValueError("Retryable error after crash")

    handler1 = handle_task_callback(is_idempotent=True)(user_func_first)
    ctx1 = create_mock_hatchet_context(
        MockContextConfig(
            task_id=signature.key,
            job_name="test_task",
            attempt_number=1,
            workflow_id=workflow_id,
        )
    )
    message = ContextMessage()

    with pytest.raises(ValueError, match="Retryable error after crash"):
        await handler1(message, ctx1)

    # Assert - cache should have only 1 entry (the pre-crash signature)
    cache = await SignatureRetryCache.aget(workflow_id)
    assert len(cache.signature_ids) == 1
    assert cache.signature_ids[0] == pre_crash_key

    # Arrange - retry: the pre-crash signature should be retrievable
    signature2, _ = await task_signature_factory(task_name="test_task_2", retries=3)

    retry_key = None

    async def user_func_retry(msg):
        nonlocal retry_key

        sig = await thirdmagic.sign("test_task", model_validators=ContextMessage)
        retry_key = sig.key
        return "success"

    handler2 = handle_task_callback(is_idempotent=True)(user_func_retry)
    ctx2 = create_mock_hatchet_context(
        MockContextConfig(
            task_id=signature2.key,
            job_name="test_task_2",
            attempt_number=2,
            workflow_id=workflow_id,
        )
    )

    # Act
    await handler2(message, ctx2)

    # Assert - the pre-crash signature is returned from cache
    assert retry_key == pre_crash_key
