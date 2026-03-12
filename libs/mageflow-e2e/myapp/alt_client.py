from unittest.mock import MagicMock

import fakeredis
from hatchet_sdk import Hatchet

from mageflow.clients.hatchet.adapter import HatchetClientAdapter
from mageflow.clients.hatchet.mageflow import HatchetMageflow
from thirdmagic.signature import Signature

# Step 1: Build a mock hatchet client with empty namespace
_alt_mock_client = MagicMock()
_alt_mock_client.config = MagicMock()
_alt_mock_client.config.logger = MagicMock()
_alt_mock_client.config.namespace = (
    ""  # CRITICAL: empty string so task names are not MagicMocks
)

# Step 2: Create real Hatchet wrapping mock client (no network connection made)
_alt_hatchet = Hatchet(client=_alt_mock_client)

# Step 3: Set global ClientAdapter BEFORE defining any tasks
Signature.ClientAdapter = HatchetClientAdapter(_alt_hatchet)

# Step 4: Create the redis client (fakeredis — no server needed)
_alt_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

# Step 5: Create HatchetMageflow instance
_alt_mf = HatchetMageflow(hatchet=_alt_hatchet, redis_client=_alt_redis)


# Step 6: Register the alt task
@_alt_mf.task(name="alt-task")
async def alt_task(msg):
    pass


# Export as `mf` for the dotted path "myapp.alt_client:mf"
mf = _alt_mf
