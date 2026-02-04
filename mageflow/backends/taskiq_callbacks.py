"""
TaskIQ task callback handler.

This module handles the Mageflow task lifecycle for TaskIQ tasks:
- Check if task should run
- Start task (update status)
- Handle success (activate callbacks)
- Handle error (activate error callbacks)
"""
import asyncio
from typing import Any, Callable

from pydantic import BaseModel

from mageflow.backends.taskiq import TaskIQExecutionContext
from mageflow.callbacks import AcceptParams, MageflowResult
from mageflow.signature.consts import TASK_ID_PARAM_NAME
from mageflow.signature.model import TaskSignature
from mageflow.signature.status import SignatureStatus
from mageflow.task.model import HatchetTaskModel
from mageflow.utils.pythonic import flexible_call


async def handle_taskiq_task(
    func: Callable,
    kwargs: dict,
    exec_ctx: TaskIQExecutionContext,
    param_config: AcceptParams = AcceptParams.NO_CTX,
) -> Any:
    """
    Handle Mageflow task lifecycle for a TaskIQ task.

    Args:
        func: The original task function
        kwargs: Cleaned kwargs (without Mageflow metadata)
        exec_ctx: TaskIQ execution context
        param_config: What params to pass to user function
    """
    task_data = exec_ctx.task_data
    task_id = task_data.get(TASK_ID_PARAM_NAME)
    signature = None

    # Check if task should run
    if task_id:
        signature = await TaskSignature.get_safe(task_id)
        if signature is None:
            exec_ctx.log(f"Task signature {task_id} not found, skipping")
            return {"Error": "Signature not found"}

        should_run = await signature.should_run()
        if not should_run:
            exec_ctx.log(f"Task {task_id} should not run, handling inactive")
            await signature.task_status.aupdate(last_status=SignatureStatus.ACTIVE)
            # Create empty message for inactive handler
            class EmptyMsg(BaseModel):
                pass
            await signature.handle_inactive_task(EmptyMsg())
            return {"Error": "Task should have been canceled"}

    try:
        # Start task (update status)
        if signature:
            async with TaskSignature.alock_from_key(task_id) as sig:
                await sig.change_status(SignatureStatus.ACTIVE)
                await sig.task_status.aupdate(worker_task_id=exec_ctx.workflow_id)

        # Call user function
        if param_config == AcceptParams.JUST_MESSAGE:
            # Get first kwarg value as message
            msg = next(iter(kwargs.values()), None)
            result = await flexible_call(func, msg)
        elif param_config == AcceptParams.NO_CTX:
            result = await flexible_call(func, **kwargs)
        else:
            # Pass execution context for logging etc.
            result = await flexible_call(func, exec_ctx, **kwargs)

    except Exception as e:
        # Handle error
        exec_ctx.log(f"Task error: {e}")

        # Check retry logic
        task_model = await HatchetTaskModel.safe_get(exec_ctx.task_name)
        should_retry = True
        if task_model:
            should_retry = task_model.should_retry(exec_ctx.attempt_number, e)

        if not should_retry and signature:
            await signature.failed()
            # Activate error callbacks
            class ErrorMsg(BaseModel):
                error: str = str(e)
            await signature.activate_error(ErrorMsg())
            # Cleanup
            await signature.remove(with_error=False)

        raise

    else:
        # Success
        if signature:
            task_results = MageflowResult(mageflow_results=result)
            dumped_results = task_results.model_dump(mode="json")

            # Activate success callbacks
            await signature.activate_success(dumped_results["mageflow_results"])
            await signature.done()
            # Cleanup
            await signature.remove(with_success=False)

        return MageflowResult(mageflow_results=result)
