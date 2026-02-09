from mageflow.callbacks import register_task, handle_task_callback
from mageflow.chain.creator import chain
from mageflow.client import Mageflow, MageflowClient, HatchetMageflow
from mageflow.init import init_mageflow_hatchet_tasks, init_mageflow_internal_tasks
from mageflow.invokers.base import TaskClientAdapter, BaseInvoker
from mageflow.signature.creator import (
    sign,
    load_signature,
    resume_task,
    lock_task,
    resume,
    pause,
    remove,
)
from mageflow.signature.status import TaskStatus
from mageflow.swarm.creator import swarm


__all__ = [
    # Core factory
    "Mageflow",
    "MageflowClient",
    # Adapter base classes
    "TaskClientAdapter",
    "BaseInvoker",
    # Signature operations
    "sign",
    "load_signature",
    "resume_task",
    "lock_task",
    "resume",
    "remove",
    "pause",
    # Task orchestration
    "chain",
    "swarm",
    # Internals
    "init_mageflow_internal_tasks",
    "init_mageflow_hatchet_tasks",
    "register_task",
    "handle_task_callback",
    "TaskStatus",
    # Backward compat
    "HatchetMageflow",
]
