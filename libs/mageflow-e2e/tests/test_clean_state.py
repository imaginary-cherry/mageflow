"""
Clean state tests: TEST-04, TEST-05, TEST-06

TEST-04: assert_nothing_dispatched passes before any dispatch call
TEST-05: dispatch records do not leak between tests (ordering matters — part1 then part2)
TEST-06: adapter.clear() resets dispatch records mid-test
"""

import mageflow
import pytest


async def test_nothing_dispatched_before_dispatch(mageflow_client):
    """TEST-04: Fresh test has zero dispatch records — assert_nothing_dispatched must pass."""
    mageflow_client.assert_nothing_dispatched()


async def test_dispatches_isolated_between_tests_part1(mageflow_client):
    """TEST-05 (first half): Dispatch a task and assert it was recorded.

    NOTE: This test intentionally leaves a dispatch record.
    test_dispatches_isolated_between_tests_part2 (defined below) must run after
    this one and verify that the record does NOT leak — pytest runs tests in
    file-definition order by default, so this ordering is load-bearing.
    """
    sig = await mageflow.asign("process-order")
    await sig.acall({"order_id": 1, "customer": "Test"})
    mageflow_client.assert_task_dispatched("process-order")


async def test_dispatches_isolated_between_tests_part2(mageflow_client):
    """TEST-05 (second half): No leakage from part1 — fresh adapter + Redis flush."""
    mageflow_client.assert_nothing_dispatched()


async def test_clear_resets_adapter(mageflow_client):
    """TEST-06: adapter.clear() resets dispatch records mid-test."""
    sig = await mageflow.asign("validate-order")
    await sig.acall({"order_id": 99})
    mageflow_client.assert_task_dispatched("validate-order")

    mageflow_client.clear()

    mageflow_client.assert_nothing_dispatched()
