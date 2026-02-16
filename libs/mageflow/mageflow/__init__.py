from thirdmagic.chain.creator import chain
from thirdmagic.signature.creator import sign
from thirdmagic.signature.model import TaskSignature
from thirdmagic.swarm.creator import swarm

from mageflow.callbacks import register_task, handle_task_callback
from mageflow.client import Mageflow
from mageflow.init import init_mageflow_hatchet_tasks

resume_task = TaskSignature.resume_from_key
lock_task = TaskSignature.alock_from_key
resume = TaskSignature.resume_from_key
pause = TaskSignature.pause_from_key
remove = TaskSignature.remove_from_key
load_signature = TaskSignature.get_safe

__all__ = [
    "load_signature",
    "resume_task",
    "lock_task",
    "resume",
    "remove",
    "pause",
    "sign",
    "init_mageflow_hatchet_tasks",
    "register_task",
    "handle_task_callback",
    "Mageflow",
    "chain",
    "swarm",
]
