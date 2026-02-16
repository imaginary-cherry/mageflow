from thirdmagic.chain.creator import chain as achain
from thirdmagic.signature import sign as asign, TaskSignature
from thirdmagic.swarm.creator import swarm as aswarm

from mageflow.callbacks import register_task, handle_task_callback
from mageflow.client import Mageflow

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
    "asign",
    "register_task",
    "handle_task_callback",
    "Mageflow",
    "achain",
    "aswarm",
]
