from typing import Any, TYPE_CHECKING

from hatchet_sdk import Hatchet, NonRetryableException
from hatchet_sdk.clients.admin import TriggerWorkflowOptions
from hatchet_sdk.runnables.workflow import BaseWorkflow
from pydantic import BaseModel, TypeAdapter
from thirdmagic.clients.base import BaseClientAdapter
from thirdmagic.clients.inner_task_names import (
    ON_CHAIN_END,
    ON_CHAIN_ERROR,
    ON_SWARM_ITEM_DONE,
    ON_SWARM_ITEM_ERROR,
    ON_SWARM_START,
)
from thirdmagic.consts import TASK_ID_PARAM_NAME
from thirdmagic.task import MageflowTaskDefinition

from mageflow.chain.messages import ChainCallbackMessage, ChainErrorMessage
from mageflow.clients.hatchet.workflow import MageflowWorkflow
from mageflow.swarm.messages import SwarmMessage, SwarmResultsMessage, SwarmErrorMessage

if TYPE_CHECKING:
    from thirdmagic.signature.model import TaskSignature
    from thirdmagic.chain.model import ChainTaskSignature
    from thirdmagic.swarm.model import SwarmTaskSignature


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
        original_msg: Any,
        error: Exception,
        chain: "ChainTaskSignature",
        failed_task: TaskSignature,
    ):
        chain_err_msg = ChainErrorMessage(
            chain_task_id=chain.key,
            error=str(error),
            original_msg=original_msg.model_dump(mode="json"),
            error_task_key=failed_task.key,
        )
        stub = self.hatchet.stubs.task(
            name=ON_CHAIN_ERROR, input_validator=ChainErrorMessage
        )
        return await stub.aio_run_no_wait(chain_err_msg)

    async def astart_swarm(
        self,
        swarm: "SwarmTaskSignature",
        options: TriggerWorkflowOptions = None,
        **kwargs,
    ):
        start_swarm_msg = SwarmMessage(swarm_task_id=swarm.key)
        params = dict(options=options) if options else {}
        stub = self.hatchet.stubs.task(
            name=ON_SWARM_START, input_validator=SwarmMessage
        )
        return await stub.aio_run_no_wait(start_swarm_msg, **params)

    async def acall_swarm_item_done(
        self, results: Any, swarm: "SwarmTaskSignature", swarm_item: "TaskSignature"
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
        self, error: Exception, swarm: "SwarmTaskSignature", swarm_item: "TaskSignature"
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

    async def acall_signature(
        self,
        signature: "TaskSignature",
        msg: Any,
        set_return_field: bool,
        options: TriggerWorkflowOptions = None,
        **kwargs,
    ):
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
