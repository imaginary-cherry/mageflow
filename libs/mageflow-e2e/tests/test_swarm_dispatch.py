"""TEST-03: SwarmTaskSignature dispatch + swarm assertion.

Validates that swarm.acall() dispatches via afill_swarm and records a
SwarmDispatchRecord with expected sub-task names via the public mageflow API.
"""

import mageflow


async def test_swarm_dispatched_with_expected_tasks(mageflow_client):
    sig_validate = await mageflow.asign("validate-order")
    sig_charge = await mageflow.asign("charge-payment")

    swarm_sig = await mageflow.aswarm(
        tasks=[sig_validate.key, sig_charge.key],
        task_name="order-swarm",
    )
    await swarm_sig.acall({})

    record = mageflow_client.assert_swarm_dispatched(
        "order-swarm", expected_task_names=["validate-order", "charge-payment"]
    )
    assert record.swarm_name == "order-swarm"
    assert set(record.task_names) == {"validate-order", "charge-payment"}
