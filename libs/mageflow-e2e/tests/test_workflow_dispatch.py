"""
Test that a signed Hatchet workflow dispatch is recorded
and assertable via mageflow_client.assert_task_dispatched.
"""

from myapp.client import OrderInput

import mageflow


async def test_workflow_dispatched_via_aio_run_no_wait(mageflow_client):
    sig = await mageflow.asign("order-workflow")
    await sig.aio_run_no_wait(OrderInput(order_id=1, customer="Alice"))

    record = mageflow_client.assert_task_dispatched("order-workflow", {"order_id": 1})
    assert record.task_name == "order-workflow"


async def test_workflow_dispatched_via_aio_run(mageflow_client):
    sig = await mageflow.asign("order-workflow")
    await sig.aio_run(OrderInput(order_id=2, customer="Bob"))

    record = mageflow_client.assert_task_dispatched("order-workflow", {"order_id": 2})
    assert record.task_name == "order-workflow"
