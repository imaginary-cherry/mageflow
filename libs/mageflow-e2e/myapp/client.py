import base64
import json
import os

from hatchet_sdk import Hatchet
from pydantic import BaseModel
from redis.asyncio import Redis

from mageflow.clients.hatchet.adapter import HatchetClientAdapter
from mageflow.clients.hatchet.mageflow import HatchetMageflow
from thirdmagic.signature import Signature

# Provide default environment variables so the module can be imported in
# development and test environments that don't have a live Hatchet server.
# In production, set HATCHET_CLIENT_TOKEN to a real token instead.
def _make_dev_token() -> str:
    """Build a minimal JWT-shaped token with local server addresses."""
    claims = {
        "sub": "dev-tenant",
        "server_url": "http://localhost:8080",
        "grpc_broadcast_address": "localhost:7070",
    }
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').decode().rstrip("=")
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"{header}.{payload}.dev"


os.environ.setdefault("HATCHET_CLIENT_TOKEN", _make_dev_token())
os.environ.setdefault("HATCHET_CLIENT_TLS_STRATEGY", "none")

# Step 1: Create a Hatchet instance (uses HATCHET_CLIENT_TOKEN env var)
hatchet = Hatchet(debug=True)

# Step 2: Set global ClientAdapter BEFORE defining any tasks
Signature.ClientAdapter = HatchetClientAdapter(hatchet)

# Step 3: Create the Redis client (connects to localhost:6379 by default)
redis_client = Redis(host="localhost", port=6379, decode_responses=True)

# Step 4: Create HatchetMageflow instance
mf = HatchetMageflow(hatchet=hatchet, redis_client=redis_client)


# Step 5: Register tasks using @mf.task() — AFTER ClientAdapter is set
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
