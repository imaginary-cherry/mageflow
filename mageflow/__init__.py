"""
MageFlow - Backend-agnostic task orchestration framework.

MageFlow provides a unified API for task orchestration that works with
multiple backends (Hatchet, TaskIQ) through dependency injection.

Example usage with Hatchet:
    from hatchet_sdk import Hatchet
    from mageflow import Mageflow

    mageflow = Mageflow(Hatchet())

    @mageflow.task(name="process-data")
    async def process_data(msg: ProcessData):
        return {"processed": msg.data}

Example usage with TaskIQ:
    from taskiq import InMemoryBroker
    from mageflow import Mageflow, BackendType

    mageflow = Mageflow(InMemoryBroker(), backend=BackendType.TASKIQ)

    @mageflow.task(name="process-data")
    async def process_data(msg: ProcessData):
        return {"processed": msg.data}
"""

from mageflow.backends.base import BackendType, BackendClient, TaskContext
from mageflow.callbacks import register_task, handle_task_callback, AcceptParams
from mageflow.chain.creator import chain
from mageflow.client import (
    Mageflow,
    BaseMageflow,
    HatchetMageflow,
    TaskIQMageflow,
)
from mageflow.init import init_mageflow_hatchet_tasks
from mageflow.signature.creator import (
    sign,
    load_signature,
    resume_task,
    lock_task,
    resume,
    pause,
)
from mageflow.signature.model import TaskSignature
from mageflow.signature.status import TaskStatus
from mageflow.swarm.creator import swarm


__all__ = [
    # Factory and client classes
    "Mageflow",
    "BaseMageflow",
    "HatchetMageflow",
    "TaskIQMageflow",
    # Backend types
    "BackendType",
    "BackendClient",
    "TaskContext",
    "AcceptParams",
    # Signature operations
    "sign",
    "load_signature",
    "resume_task",
    "lock_task",
    "resume",
    "pause",
    "TaskSignature",
    "TaskStatus",
    # Orchestration
    "chain",
    "swarm",
    # Registration
    "register_task",
    "handle_task_callback",
    "init_mageflow_hatchet_tasks",
]
