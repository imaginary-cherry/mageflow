"""
Marker override test: TEST-07

TEST-07: @pytest.mark.mageflow(client=...) overrides default client and loads alt_client task_defs
"""

import mageflow
import pytest


@pytest.mark.mageflow(client="myapp.alt_client:mf")
async def test_marker_override_resolves_alt_client(mageflow_client):
    """TEST-07: Marker override loads alt_client's task_defs instead of default client's."""
    task_sig = await mageflow.asign("alt-task")
    await task_sig.acall({})
    mageflow_client.assert_task_dispatched("alt-task")
