from typing import Any, cast

import rapyer
from hatchet_sdk import Hatchet, NonRetryableException, Context
from hatchet_sdk.clients.admin import TriggerWorkflowOptions
from hatchet_sdk.runnables.contextvars import ctx_additional_metadata
from hatchet_sdk.runnables.types import EmptyModel
from hatchet_sdk.runnables.workflow import BaseWorkflow
from pydantic import BaseModel, TypeAdapter
from rapyer.fields import RapyerKey
from thirdmagic.chain import ChainTaskSignature
from thirdmagic.clients.base import BaseClientAdapter
from thirdmagic.consts import TASK_ID_PARAM_NAME
from thirdmagic.signature import Signature
from thirdmagic.swarm import SwarmTaskSignature
from thirdmagic.task import TaskSignature
from thirdmagic.task_def import MageflowTaskDefinition

from mageflow.chain.messages import ChainCallbackMessage, ChainErrorMessage
from mageflow.clients.hatchet.workflow import MageflowWorkflow
from mageflow.clients.inner_task_names import (
    ON_CHAIN_END,
    ON_CHAIN_ERROR,
    ON_SWARM_ITEM_DONE,
    ON_SWARM_ITEM_ERROR,
)
from mageflow.clients.inner_task_names import SWARM_FILL_TASK
from mageflow.lifecycle.signature import SignatureLifecycle
from mageflow.lifecycle.task import TaskLifecycle
from mageflow.swarm.messages import (
    SwarmMessage,
    SwarmResultsMessage,
    SwarmErrorMessage,
    FillSwarmMessage,
)


class HatchetClientAdapter(BaseClientAdapter):
    def __init__(self, hatchet: Hatchet):
        self.hatchet = hatchet

    def task_ctx(self, signature: "TaskSignature") -> dict:
        return {TASK_ID_PARAM_NAME: signature.key}

    def _update_options(
        self, signature: "TaskSignature", options: TriggerWorkflowOptions = None
    ):
        options = options or TriggerWorkflowOptions()
        task_ctx = self.task_ctx(signature)
        options.additional_metadata |= task_ctx
        return options

    async def acall_chain_done(self, results: Any, chain: "ChainTaskSignature"):
        chain_end_msg = ChainCallbackMessage(
            chain_results=results, chain_task_id=chain.key
        )
        stub = self.hatchet.stubs.task(
            name=ON_CHAIN_END, input_validator=ChainCallbackMessage
        )
        return await stub.aio_run_no_wait(chain_end_msg)

    async def acall_chain_error(
        self,
        original_msg: dict,
        error: Exception,
        chain: "ChainTaskSignature",
        failed_task: "Signature",
    ):
        chain_err_msg = ChainErrorMessage(
            chain_task_id=chain.key,
            error=str(error),
            original_msg=original_msg,
            error_task_key=failed_task.key,
        )
        stub = self.hatchet.stubs.task(
            name=ON_CHAIN_ERROR, input_validator=ChainErrorMessage
        )
        return await stub.aio_run_no_wait(chain_err_msg)

    async def afill_swarm(
        self,
        swarm: "SwarmTaskSignature",
        max_tasks: int = None,
        options: TriggerWorkflowOptions = None,
        **kwargs,
    ):
        start_swarm_msg = FillSwarmMessage(swarm_task_id=swarm.key, max_tasks=max_tasks)
        params = dict(options=options) if options else {}
        stub = self.hatchet.stubs.task(
            name=SWARM_FILL_TASK, input_validator=FillSwarmMessage
        )
        return await stub.aio_run_no_wait(start_swarm_msg, **params)

    async def acall_swarm_item_done(
        self, results: Any, swarm: "SwarmTaskSignature", swarm_item: "Signature"
    ):
        swarm_done_msg = SwarmResultsMessage(
            swarm_task_id=swarm.key,
            swarm_item_id=swarm_item.key,
            mageflow_results=results,
        )
        stub = self.hatchet.stubs.task(
            name=ON_SWARM_ITEM_DONE, input_validator=SwarmResultsMessage
        )
        return await stub.aio_run_no_wait(swarm_done_msg)

    async def acall_swarm_item_error(
        self, error: Exception, swarm: "SwarmTaskSignature", swarm_item: "Signature"
    ):
        swarm_error_msg = SwarmErrorMessage(
            swarm_task_id=swarm.key, swarm_item_id=swarm_item.key, error=str(error)
        )
        stub = self.hatchet.stubs.task(
            name=ON_SWARM_ITEM_ERROR, input_validator=SwarmErrorMessage
        )
        return await stub.aio_run_no_wait(swarm_error_msg)

    def extract_validator(self, client_task: BaseWorkflow) -> type[BaseModel]:
        validator = client_task.input_validator
        if isinstance(validator, TypeAdapter):
            validator = validator._type
        return validator

    def extract_retries(self, client_task: BaseWorkflow) -> int:
        return client_task.tasks[0].retries

    async def acall_signature(
        self,
        signature: TaskSignature,
        msg: Any,
        set_return_field: bool,
        options: TriggerWorkflowOptions = None,
        **kwargs,
    ):
        if msg is None:
            msg = EmptyModel()
        options = self._update_options(signature, options)
        total_kwargs = signature.kwargs | kwargs
        workflow = self.hatchet.workflow(
            name=signature.task_name, input_validator=signature.model_validators
        )
        mageflow_wf = MageflowWorkflow(
            workflow,
            total_kwargs,
            signature.return_field_name if set_return_field else None,
        )
        return await mageflow_wf.aio_run_no_wait(msg, options)

    def should_task_retry(
        self, task_definition: MageflowTaskDefinition, attempt_num: int, e: Exception
    ) -> bool:
        finish_retry = (
            task_definition.retries is not None
            and attempt_num < task_definition.retries
        )
        return finish_retry and not isinstance(e, NonRetryableException)

    def task_name(self, task: BaseWorkflow) -> str:
        return task.name

    async def create_lifecycle(self, message: BaseModel, ctx: Context):
        task_key = ctx.additional_metadata.get(TASK_ID_PARAM_NAME, None)
        if task_key is None:
            return TaskLifecycle()

        hatchet_ctx_metadata = ctx_additional_metadata.get() or {}
        hatchet_ctx_metadata.pop(TASK_ID_PARAM_NAME, None)
        ctx_additional_metadata.set(hatchet_ctx_metadata)

        signature = await rapyer.afind_one(task_key)
        if not signature:
            raise NonRetryableException("Signature was deleted, we can't run the task")

        signature = cast(Signature, signature)
        container = None
        if signature.signature_container_id:
            container = await rapyer.aget(signature.signature_container_id)

        return SignatureLifecycle(ctx.workflow_id, signature, container)

    async def lifecycle_from_signature(
        self, message: BaseModel, ctx: Context, signature_key: RapyerKey
    ):
        signature = await rapyer.afind_one(signature_key)
        if not signature:
            return None
        signature = cast(Signature, signature)
        container = None
        if signature.signature_container_id:
            container = await rapyer.aget(signature.signature_container_id)
        return SignatureLifecycle(ctx.workflow_id, signature, container)
