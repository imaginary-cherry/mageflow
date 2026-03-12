"""TEST-01: TaskSignature dispatch + partial input match.

Validates the public mageflow.asign() API records dispatches correctly
and that TestClientAdapter assertion methods work with partial and full input.
"""

import mageflow


async def test_process_order_dispatched(mageflow_client):
    mageflow_client.assert_nothing_dispatched()

    task_sig = await mageflow.asign("process-order")
    await task_sig.acall({"order_id": 42, "customer": "Alice"})

    record = mageflow_client.assert_task_dispatched("process-order", {"order_id": 42})
    assert record.task_name == "process-order"


async def test_task_dispatched_with_full_input(mageflow_client):
    task_sig = await mageflow.asign("process-order")
    await task_sig.acall({"order_id": 99, "customer": "Bob"})

    mageflow_client.assert_task_dispatched(
        "process-order", {"order_id": 99, "customer": "Bob"}
    )


async def test_plain_task_dispatched(mageflow_client):
    task_sig = await mageflow.asign("validate-order")
    await task_sig.acall({"order_id": 1})

    mageflow_client.assert_task_dispatched("validate-order")
