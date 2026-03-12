"""TEST-02: ChainTaskSignature dispatch + first-task verification.

Validates that chain.acall() dispatches the first task in the chain via the
public mageflow API and that TestClientAdapter records it as a TaskDispatchRecord.
"""

import mageflow


async def test_chain_first_task_dispatched(mageflow_client):
    sig_validate = await mageflow.asign("validate-order")
    sig_charge = await mageflow.asign("charge-payment")

    chain_sig = await mageflow.achain(
        tasks=[sig_validate.key, sig_charge.key],
        name="order-pipeline",
    )
    await chain_sig.acall({"order_id": 456})

    record = mageflow_client.assert_task_dispatched("validate-order")
    assert record.task_name == "validate-order"
