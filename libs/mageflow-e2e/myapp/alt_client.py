import base64
import json
import os

from hatchet_sdk import Hatchet
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
_alt_hatchet = Hatchet(debug=True)

# Step 2: Set global ClientAdapter BEFORE defining any tasks
Signature.ClientAdapter = HatchetClientAdapter(_alt_hatchet)

# Step 3: Create the Redis client (connects to localhost:6379 by default)
_alt_redis = Redis(host="localhost", port=6379, decode_responses=True)

# Step 4: Create HatchetMageflow instance
_alt_mf = HatchetMageflow(hatchet=_alt_hatchet, redis_client=_alt_redis)


# Step 5: Register the alt task
@_alt_mf.task(name="alt-task")
async def alt_task(msg):
    pass


# Export as `mf` for the dotted path "myapp.alt_client:mf"
mf = _alt_mf
