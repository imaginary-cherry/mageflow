import os
from typing import TypeVar, overload

import redis
from hatchet_sdk import Hatchet
from redis.asyncio import Redis

from mageflow.callbacks import AcceptParams
from mageflow.clients.hatchet.mageflow import HatchetMageflow
from mageflow.invokers.hatchet import HatchetInvoker
from mageflow.startup import mageflow_config

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

    # Create a hatchet client with empty namespace for creating wf
    config = hatchet_client._client.config.model_copy(deep=True)
    config.namespace = ""
    hatchet_caller = Hatchet(config=config, debug=hatchet_client._client.debug)
    mageflow_config.hatchet_client = hatchet_caller
    # TODO - we should get rid of the hatchet caller, just use a unify namespace, this is hatchet pattern, use it
    HatchetInvoker.client = hatchet_client

    if redis_client is None:
        redis_url = os.getenv("REDIS_URL")
        redis_client = redis.asyncio.from_url(redis_url, decode_responses=True)
    if isinstance(redis_client, str):
        redis_client = redis.asyncio.from_url(redis_client, decode_responses=True)
    mageflow_config.redis_client = redis_client
    return HatchetMageflow(hatchet_client, redis_client, param_config)
