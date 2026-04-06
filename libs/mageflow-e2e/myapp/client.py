from hatchet_sdk import Hatchet
from pydantic import BaseModel
from redis.asyncio import Redis

from mageflow.clients.hatchet.adapter import HatchetClientAdapter
from mageflow.clients.hatchet.mageflow import HatchetMageflow
from myapp.init import hatchet, redis_client
from thirdmagic.signature import Signature

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


@mf.durable_task(name="durable-process")
async def durable_process(msg):
    pass


# Step 6: Register a DAG workflow
order_workflow = mf.workflow(name="order-workflow", input_validator=OrderInput)


@order_workflow.task()
async def step_one(msg):
    return {"step": 1}


@order_workflow.task(parents=[step_one])
async def step_two(msg):
    return {"step": 2}
