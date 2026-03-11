import dataclasses
from typing import Any, TYPE_CHECKING

from pydantic import BaseModel, TypeAdapter, ValidationError

from thirdmagic.clients.base import BaseClientAdapter
from thirdmagic.clients.lifecycle import BaseLifecycle
from thirdmagic.task_def import MageflowTaskDefinition

if TYPE_CHECKING:
    from thirdmagic.chain.model import ChainTaskSignature
    from thirdmagic.signature import Signature
    from thirdmagic.swarm.model import SwarmTaskSignature
    from thirdmagic.task import TaskSignature
    from thirdmagic.utils import HatchetTaskType


@dataclasses.dataclass
class RecordedDispatch:
    dispatch_type: str
    signature_or_name: str
    input_data: Any
    kwargs: dict


class _StubRunRef:
    workflow_run_id: str = "test-stub-run-id"

    async def aio_result(self) -> dict:
        return {}


class TestClientAdapter(BaseClientAdapter):
    def __init__(self, task_defs: dict[str, MageflowTaskDefinition] | None = None):
        self._dispatches: list[RecordedDispatch] = []
        self._task_defs: dict[str, MageflowTaskDefinition] = task_defs or {}

    # ------------------------------------------------------------------
    # Helper: input validation
    # ------------------------------------------------------------------

    def _validate_input(self, task_name: str, msg: Any) -> None:
        task_def = self._task_defs.get(task_name)
        if task_def is None:
            return
        validator = self.extract_validator(task_def)
        if validator is BaseModel:
            return
        try:
            validator.model_validate(msg)
        except ValidationError as e:
            raise ValueError(
                f"Dispatch input validation failed for task '{task_name}': {e}"
            )

    # ------------------------------------------------------------------
    # BaseClientAdapter abstract methods
    # ------------------------------------------------------------------

    def extract_validator(self, client_task) -> type[BaseModel]:
        validator = getattr(client_task, "input_validator", None)
        if validator is None:
            return BaseModel
        if isinstance(validator, TypeAdapter):
            validator = validator._type
        return validator

    def extract_retries(self, client_task) -> int:
        return getattr(client_task, "retries", 0) or 0

    async def acall_signature(
        self,
        signature: "TaskSignature",
        msg: Any,
        set_return_field: bool,
        **kwargs,
    ):
        self._validate_input(signature.task_name, msg)
        self._dispatches.append(
            RecordedDispatch(
                dispatch_type="signature",
                signature_or_name=signature.task_name,
                input_data=msg,
                kwargs=kwargs,
            )
        )
        return _StubRunRef()

    async def await_signature(
        self,
        signature: "TaskSignature",
        msg: Any,
        set_return_field: bool,
        **kwargs,
    ):
        self._validate_input(signature.task_name, msg)
        self._dispatches.append(
            RecordedDispatch(
                dispatch_type="await_signature",
                signature_or_name=signature.task_name,
                input_data=msg,
                kwargs=kwargs,
            )
        )
        return {}

    async def acall_chain_done(self, results: Any, chain: "ChainTaskSignature"):
        self._dispatches.append(
            RecordedDispatch(
                dispatch_type="chain_done",
                signature_or_name=chain.key,
                input_data=results,
                kwargs={},
            )
        )
        return _StubRunRef()

    async def acall_chain_error(
        self,
        original_msg: dict,
        error: BaseException,
        chain: "ChainTaskSignature",
        failed_task: "Signature",
    ):
        self._dispatches.append(
            RecordedDispatch(
                dispatch_type="chain_error",
                signature_or_name=chain.key,
                input_data={
                    "original_msg": original_msg,
                    "error": str(error),
                    "failed_task_key": failed_task.key,
                },
                kwargs={},
            )
        )
        return _StubRunRef()

    async def afill_swarm(
        self, swarm: "SwarmTaskSignature", max_tasks: int = None, **kwargs
    ):
        self._dispatches.append(
            RecordedDispatch(
                dispatch_type="swarm_fill",
                signature_or_name=swarm.key,
                input_data={"max_tasks": max_tasks},
                kwargs=kwargs,
            )
        )
        return _StubRunRef()

    async def acall_swarm_item_done(
        self, results: Any, swarm: "SwarmTaskSignature", swarm_item: "Signature"
    ):
        self._dispatches.append(
            RecordedDispatch(
                dispatch_type="swarm_item_done",
                signature_or_name=swarm.key,
                input_data={"results": results, "swarm_item_key": swarm_item.key},
                kwargs={},
            )
        )
        return _StubRunRef()

    async def acall_swarm_item_error(
        self, error: BaseException, swarm: "SwarmTaskSignature", swarm_item: "Signature"
    ):
        self._dispatches.append(
            RecordedDispatch(
                dispatch_type="swarm_item_error",
                signature_or_name=swarm.key,
                input_data={"error": str(error), "swarm_item_key": swarm_item.key},
                kwargs={},
            )
        )
        return _StubRunRef()

    def should_task_retry(
        self,
        task_definition: MageflowTaskDefinition,
        attempt_num: int,
        e: BaseException,
    ) -> bool:
        return False

    def task_name(self, task: "HatchetTaskType") -> str:
        return task.name

    async def create_lifecycle(self, *args) -> BaseLifecycle:
        from mageflow.lifecycle.task import TaskLifecycle

        return TaskLifecycle()

    async def lifecycle_from_signature(self, *args) -> BaseLifecycle:
        return None

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @property
    def dispatches(self) -> list[RecordedDispatch]:
        return list(self._dispatches)

    def clear(self) -> None:
        self._dispatches.clear()
