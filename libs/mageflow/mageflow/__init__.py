import rapyer
from rapyer.fields import RapyerKey

from mageflow.callbacks import handle_task_callback
from mageflow.client import Mageflow
from mageflow.config import MageflowConfig, SignatureTTLConfig, TTLConfig
from mageflow.startup import start_mageflow
from thirdmagic.chain.creator import chain as achain
from thirdmagic.signature import Signature
from thirdmagic.swarm.creator import swarm as aswarm
from thirdmagic.task import TaskSignature
from thirdmagic.task import sign as asign

resume_task = TaskSignature.resume_from_key
lock_task = TaskSignature.alock_from_key
resume = TaskSignature.resume_from_key
pause = TaskSignature.pause_from_key
remove = TaskSignature.remove_from_key


async def load_sign(key: RapyerKey) -> Signature:
    return await rapyer.afind_one(key)


load_signature = rapyer.afind_one
abounded_field = rapyer.apipeline


__all__ = [
    "load_signature",
    "resume_task",
    "lock_task",
    "resume",
    "remove",
    "pause",
    "asign",
    "handle_task_callback",
    "Mageflow",
    "MageflowConfig",
    "TTLConfig",
    "SignatureTTLConfig",
    "achain",
    "aswarm",
    "start_mageflow",
    "abounded_field",
]
