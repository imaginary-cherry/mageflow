from typing import Any, TYPE_CHECKING

from hatchet_sdk import Hatchet
from hatchet_sdk.runnables.workflow import BaseWorkflow
from pydantic import BaseModel, TypeAdapter

from thirdmagic.clients.base import BaseClientAdapter
from thirdmagic.task import MageflowTaskDefinition
from thirdmagic.utils import HatchetTaskType

if TYPE_CHECKING:
    from thirdmagic.signatures.siganture import TaskSignature


class HatchetClientAdapter(BaseClientAdapter):
    def __init__(self, hatchet: Hatchet):
        self.hatchet = hatchet

    def extract_validator(self, client_task: BaseWorkflow) -> type[BaseModel]:
        validator = client_task.input_validator
        if isinstance(validator, TypeAdapter):
            validator = validator._type
        return validator

    async def acall_task_identifier(self, task_id: str, **kwargs):
        workflow = self.hatchet.workflow(name=task_id)

    async def acall_signature(
        self, signature: "TaskSignature", msg: Any, set_return_field: bool, **kwargs
    ):
        pass

    def should_task_retry(
        self, task_definition: MageflowTaskDefinition, attempt_num: int, e: Exception
    ) -> bool:
        pass

    def task_name(self, task: HatchetTaskType) -> str:
        pass
