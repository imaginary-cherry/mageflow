# Testing

<div style="background: linear-gradient(135deg, #7c4dff 0%, #b388ff 100%); color: white; padding: 16px 20px; border-radius: 8px; margin-bottom: 20px;">
  <strong style="font-size: 1.1em;">🧪 Beta Feature</strong><br>
  <span style="opacity: 0.95;">The testing module is currently experimental. The API may change in future releases based on feedback.</span>
</div>

MageFlow ships with a pytest plugin that lets you test your task dispatching logic **without running Hatchet or any external services**. It replaces the real client adapter with `TestClientAdapter` — an in-memory adapter that records every dispatch and exposes assertion helpers.

## Setup

### 1. Register the plugin

Add the plugin to your `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
plugins = ["mageflow.testing.plugin"]
```

### 2. Configure the client (optional)

Point the plugin to your real `Mageflow` client so it can load task definitions and validate inputs at dispatch time:

```toml
[tool.mageflow.testing]
client = "myapp.client:mageflow_client"
```

`client` accepts a dotted import path (`module.path:attribute` or `module.path.attribute`).

If omitted, the adapter runs without input validation.

### 3. Choose a Redis backend

The plugin needs a Redis connection for `rapyer` models. Pick one:

| Backend | Config value | Description |
|---------|-------------|-------------|
| **testcontainers** (default) | `"testcontainers"` | Spins up a real Redis container per session via `testcontainers` |
| **fakeredis** | `"fakeredis"` | Uses an in-memory fake — no Docker required |

Set it in `pyproject.toml`:

```toml
[tool.mageflow.testing]
backend = "fakeredis"
```

Or via environment variable:

```bash
MAGEFLOW_TESTING_BACKEND=fakeredis pytest
```

## The `mageflow_client` fixture

Inject `mageflow_client` into any async test. It provides a `TestClientAdapter` instance that is scoped per test function — dispatches are isolated between tests.

```python
import pytest
import mageflow

@pytest.mark.asyncio
async def test_order_flow(mageflow_client):
    sig = await mageflow.asign("process-order", model_validators=BaseModel)
    await sig.acall({"order_id": 123})

    mageflow_client.assert_task_dispatched("process-order", {"order_id": 123})
```

### Per-test overrides with `@pytest.mark.mageflow`

Override plugin-level settings for a specific test:

```python
@pytest.mark.mageflow(client="myapp.other_client:client", local_execution=True)
@pytest.mark.asyncio
async def test_with_different_client(mageflow_client):
    ...
```

## Asserting dispatches

### Tasks

```python
# Assert a task was dispatched (partial input match by default)
record = mageflow_client.assert_task_dispatched("send-email", {"to": "user@test.com"})

# Exact input match
mageflow_client.assert_task_dispatched("send-email", full_input_dict, exact=True)
```

The returned `TaskDispatchRecord` has `task_name`, `input_data`, and `kwargs` fields.

### Swarms

```python
mageflow_client.assert_swarm_dispatched(
    "image-processing",
    expected_task_names=["resize-image", "compress-image"],
)
```

### Chains

```python
mageflow_client.assert_chain_dispatched(
    "order-pipeline",
    expected_task_names=["validate-order", "charge-payment"],
)
```

!!! note
    `assert_chain_dispatched` only fires when the chain completes via the callback flow (`acall_chain_done`). Calling `chain.acall()` dispatches the **first task** in the chain — use `assert_task_dispatched` to verify that.

### Nothing dispatched

```python
mageflow_client.assert_nothing_dispatched()
```

## Inspecting dispatches

Access the recorded dispatches directly for custom assertions:

```python
# Typed lists filtered by dispatch type
mageflow_client.task_dispatches    # list[TaskDispatchRecord]
mageflow_client.swarm_dispatches   # list[SwarmDispatchRecord]
mageflow_client.chain_dispatches   # list[ChainDispatchRecord]

# All dispatches (untyped)
mageflow_client.dispatches         # list[RecordedDispatch]
```

## Clearing state

Reset all recorded dispatches within a test:

```python
mageflow_client.clear()
mageflow_client.assert_nothing_dispatched()  # passes
```

## Input validation

When a `client` path is configured, the adapter loads task definitions and validates dispatch inputs against their `input_validator`. If validation fails, a `ValueError` is raised immediately — catching bad inputs before they reach the task runner.
