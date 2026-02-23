import os
from typing import TypeVar, overload

import redis
from hatchet_sdk import Hatchet
from redis.asyncio import Redis
from thirdmagic.signature import Signature

from mageflow.callbacks import AcceptParams
from mageflow.clients.hatchet.adapeter import HatchetClientAdapter
from mageflow.clients.hatchet.mageflow import HatchetMageflow

T = TypeVar("T")


@overload
def Mageflow(
    hatchet_client: Hatchet, redis_client: Redis | str = None
) -> HatchetMageflow: ...


def Mageflow(
    hatchet_client: T = None,
    redis_client: Redis | str = None,
    param_config: AcceptParams = AcceptParams.NO_CTX,
) -> T:
    if hatchet_client is None:
        hatchet_client = Hatchet()

    mageflow_adapter = HatchetClientAdapter(hatchet_client)
    Signature.ClientAdapter = mageflow_adapter

    if redis_client is None:
        redis_url = os.getenv("REDIS_URL")
        redis_client = redis.asyncio.from_url(redis_url, decode_responses=True)
    if isinstance(redis_client, str):
        redis_client = redis.asyncio.from_url(redis_client, decode_responses=True)
    return HatchetMageflow(hatchet_client, redis_client, param_config)
