from orchestrator.hatchet.config import orchestrator_config
from orchestrator.hatchet.models import ContextTaskMessage
from hatchet_sdk.runnables.task import Depends


def logger_from_context_msg(msg: ContextTaskMessage, ctx):
    return get_context_logger(msg.context)


deps_logger = Depends(logger_from_context_msg)


def redis_from_config(msg, ctx):
    if not orchestrator_config.redis_client:
        raise ValueError("Redis client is not initialized")
    return orchestrator_config.redis_client


deps_redis = Depends(redis_from_config)


def hatchet_from_config(msg, ctx):
    if not orchestrator_config.hatchet_client:
        raise ValueError("Hatchet client is not initialized")
    return orchestrator_config.hatchet_client


deps_hatchet = Depends(hatchet_from_config)
