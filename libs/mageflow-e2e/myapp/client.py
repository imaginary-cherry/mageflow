from unittest.mock import MagicMock

import fakeredis
from hatchet_sdk import Hatchet
from mageflow.clients.hatchet.adapter import HatchetClientAdapter
from mageflow.clients.hatchet.mageflow import HatchetMageflow
from pydantic import BaseModel
from thirdmagic.signature import Signature

# Step 1: Build a mock hatchet client with empty namespace
_mock_client = MagicMock()
_mock_client.config = MagicMock()
_mock_client.config.logger = MagicMock()
_mock_client.config.namespace = ""  # CRITICAL: empty string so task names are not MagicMocks

# Step 2: Create real Hatchet wrapping mock client (no network connection made)
_hatchet = Hatchet(client=_mock_client)

# Step 3: Set global ClientAdapter BEFORE defining any tasks
Signature.ClientAdapter = HatchetClientAdapter(_hatchet)

# Step 4: Create the redis client (fakeredis — no server needed)
_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

# Step 5: Create HatchetMageflow instance
mf = HatchetMageflow(hatchet=_hatchet, redis_client=_redis)


# Step 6: Register tasks using @mf.task() — AFTER ClientAdapter is set
class OrderInput(BaseModel):
    order_id: int
    customer: str


@mf.task(name="process-order", input_validator=OrderInput)
async def process_order(msg: OrderInput):
    pass


@mf.task(name="validate-order")
async def validate_order(msg):
    pass


@mf.task(name="charge-payment")
async def charge_payment(msg):
    pass
