import os
import warnings
from typing import TypeVar, overload

import redis
from hatchet_sdk import Hatchet
from redis.asyncio import Redis

from mageflow.callbacks import AcceptParams
from mageflow.clients.hatchet.adapter import HatchetClientAdapter
from mageflow.clients.hatchet.mageflow import HatchetMageflow
from mageflow.config import MageflowConfig
from thirdmagic.signature import Signature

T = TypeVar("T")


@overload
def Mageflow(
    hatchet_client: Hatchet,
    redis_client: Redis | str = None,
    param_config: AcceptParams = None,
    config: MageflowConfig = None,
) -> HatchetMageflow: ...


def Mageflow(
    hatchet_client: T = None,
    redis_client: Redis | str = None,
    param_config: AcceptParams = None,
    config: MageflowConfig = None,
) -> T:
    if config is None:
        config = MageflowConfig()

    if param_config is not None:
        warnings.warn(
            "Passing 'param_config' directly to Mageflow() is deprecated. "
            "Set it via MageflowConfig(param_config=...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        config.param_config = param_config

    if hatchet_client is None:
        hatchet_client = Hatchet()

    mageflow_adapter = HatchetClientAdapter(hatchet_client)
    Signature.ClientAdapter = mageflow_adapter

    if redis_client is None:
        redis_url = os.getenv("REDIS_URL")
        redis_client = redis.asyncio.from_url(redis_url, decode_responses=True)
    if isinstance(redis_client, str):
        redis_client = redis.asyncio.from_url(redis_client, decode_responses=True)
    return HatchetMageflow(hatchet_client, redis_client, config)
