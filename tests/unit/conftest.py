import fakeredis
import pytest
import pytest_asyncio
from hatchet_sdk import Hatchet, ClientConfig

from orchestrator import TaskSignature
from orchestrator.hatchet.chain import ChainTaskSignature
from orchestrator.hatchet.swarm import SwarmTaskSignature


@pytest_asyncio.fixture
async def redis_client():
    client = fakeredis.aioredis.FakeRedis()
    await client.flushall()
    try:
        yield client
    finally:
        await client.flushall()
        await client.close()


@pytest.fixture
def hatchet_mock():
    config_obj = ClientConfig(
        token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOiJodHRwczovL2xvY2FsaG9zdCIsImV4cCI6NDkwNTQ3NzYyNiwiZ3JwY19icm9hZGNhc3RfYWRkcmVzcyI6Imh0dHBzOi8vbG9jYWxob3N0IiwiaWF0IjoxNzUxODc3NjI2LCJpc3MiOiJodHRwczovL2xvY2FsaG9zdCIsInNlcnZlcl91cmwiOiJodHRwczovL2xvY2FsaG9zdCIsInN1YiI6IjdlY2U4ZTk4LWNiMjMtNDg3Ny1hZGNlLWFmYTBiNDMxYTgyMyIsInRva2VuX2lkIjoiNjk0MjBkOGMtMTQ4NS00NGRlLWFmY2YtMDlkYzM5NmJiYzI0In0.l2yHtg1ZGJSkge6MnLXj_zGyg1w_6LZ7ZuyyNrWORnc",
        tls_strategy="tls",
    )
    hatchet = Hatchet(config=config_obj)

    yield hatchet


@pytest_asyncio.fixture(autouse=True, scope="function")
def init_models(redis_client):
    from orchestrator.hatchet.signature import SIGNATURES_NAME_MAPPING

    models = [SwarmTaskSignature, ChainTaskSignature, TaskSignature]

    SIGNATURES_NAME_MAPPING.update(
        {signature_class.__name__: signature_class for signature_class in models}
    )
    for signature_class in SIGNATURES_NAME_MAPPING.values():
        signature_class.Meta.redis = redis_client
