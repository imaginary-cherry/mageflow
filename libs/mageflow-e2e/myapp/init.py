import os

from hatchet_sdk import Hatchet
from pydantic import BaseModel
from redis.asyncio import Redis

from mageflow.clients.hatchet.adapter import HatchetClientAdapter
from mageflow.clients.hatchet.mageflow import HatchetMageflow
from myapp.utils import _make_dev_token
from thirdmagic.signature import Signature

os.environ.setdefault("HATCHET_CLIENT_TOKEN", _make_dev_token())
os.environ.setdefault("HATCHET_CLIENT_TLS_STRATEGY", "none")

# Step 1: Create a Hatchet instance (uses HATCHET_CLIENT_TOKEN env var)
hatchet = Hatchet(debug=True)

# Step 2: Set global ClientAdapter BEFORE defining any tasks
Signature.ClientAdapter = HatchetClientAdapter(hatchet)

# Step 3: Create the Redis client (connects to localhost:6379 by default)
redis_client = Redis(host="localhost", port=6379, decode_responses=True)
