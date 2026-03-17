from hatchet_sdk import Hatchet
from redis.asyncio import Redis

from mageflow.clients.hatchet.adapter import HatchetClientAdapter
from mageflow.clients.hatchet.mageflow import HatchetMageflow
from myapp.init import hatchet
from thirdmagic.signature import Signature

# Step 3: Create the Redis client (connects to localhost:6379 by default)
_alt_redis = Redis(host="localhost", port=6379, decode_responses=True)

# Step 4: Create HatchetMageflow instance
_alt_mf = HatchetMageflow(hatchet=hatchet, redis_client=_alt_redis)


# Step 5: Register the alt task
@_alt_mf.task(name="alt-task")
async def alt_task(msg):
    pass


# Export as `mf` for the dotted path "myapp.alt_client:mf"
mf = _alt_mf
