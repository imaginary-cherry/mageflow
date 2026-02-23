from thirdmagic.chain.model import ChainTaskSignature
from thirdmagic.signature.model import TaskInputType
from thirdmagic.task.creator import resolve_signatures, TaskSignatureConvertible


async def chain(
    tasks: list[TaskSignatureConvertible],
    name: str = None,
    error: TaskInputType = None,
    success: TaskInputType = None,
    **kwargs,
) -> ChainTaskSignature:
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

    return chain_task_signature
