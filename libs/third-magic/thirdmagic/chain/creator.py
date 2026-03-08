from thirdmagic.chain.model import ChainTaskSignature
from thirdmagic.signature.model import TaskInputType
from thirdmagic.signature.retry_cache import (
    cache_signature,
    get_cached_signature,
    retry_cache_ctx,
)
from thirdmagic.task.creator import TaskSignatureConvertible, resolve_signatures


async def chain(
    tasks: list[TaskSignatureConvertible],
    name: str = None,
    error: TaskInputType = None,
    success: TaskInputType = None,
    **kwargs,
) -> ChainTaskSignature:
    cache_state = retry_cache_ctx.get()
    if cache_state and cache_state.is_retry and cache_state.cache:
        cached = await get_cached_signature(cache_state, ChainTaskSignature)
        if cached is not None:
            return cached

    if len(tasks) < 2:
        raise ValueError(
            "Chained tasks must contain at least two tasks. "
            "If you want to run a single task, use `create_workflow` instead."
        )
    tasks = await resolve_signatures(tasks)

    # Create a chain task that will be deleted only at the end of the chain
    first_task = tasks[0]
    chain_task_signature = ChainTaskSignature(
        task_name=f"chain-task:{name or first_task.task_name}",
        success_callbacks=[success] if success else [],
        error_callbacks=[error] if error else [],
        tasks=tasks,
        kwargs=kwargs,
    )
    async with first_task.apipeline():
        for task in tasks:
            task.signature_container_id = chain_task_signature.key
        await chain_task_signature.asave()

    if cache_state and not cache_state.is_retry:
        await cache_signature(cache_state, chain_task_signature)

    return chain_task_signature
