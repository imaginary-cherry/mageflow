# Task Lifecycle Management

MageFlow provides comprehensive lifecycle management capabilities that allow you to control task execution at runtime. You can suspend, interrupt, and resume tasks based on your application's requirements.

## Overview

Task lifecycle management includes three primary operations:

- **Suspend**: Gracefully stops a task only if it hasn't started execution yet
- **Interrupt**: Aggressively stops a task regardless of its current status
- **Resume**: Restarts a previously suspended or interrupted task

## Suspend

The `suspend` operation provides a graceful way to stop tasks that are still in a pending state.

### Behavior
- Tasks that are queued but haven't started execution will be stopped
- Tasks that are already running will not be stopped (chain and swarm will stop after they have started, however a single task will not)

### Usage
```python
await task_signature.suspend()

await chain_workflow.suspend()

await swarm_workflow.suspend()
```

## Interrupt

The `interrupt` operation aggressively stops tasks regardless of their current execution status.

!!! warning "Aggressive Action Warning"
    Using `interrupt` is an aggressive action that forcefully stops task execution. We cannot guarantee that interrupted tasks can be properly resumed later, as the task state may be left in an inconsistent condition.

### Behavior
- Will stop tasks at any point in the task lifecycle, even after it started running
- Resuming interrupted tasks may not work reliably

### Usage
```python
await task_signature.interrupt()

await chain_workflow.interrupt()

await swarm_workflow.interrupt()
```

## Resume

The `resume` operation restarts previously suspended or interrupted tasks.

### Behavior
- Reliable for suspended tasks that were cleanly suspended
- Uncertain for interrupted tasks that were forcefully interrupted (may have inconsistent state)

### Usage
```python
await task_signature.resume()

await chain_workflow.resume()

await swarm_workflow.resume()
```

## Best Practices

### Prefer Suspend Over Interrupt
Always try to use `suspend` first, as it provides a cleaner shutdown:

```python
try:
    await workflow.suspend()
except TaskAlreadyRunningError:
    await workflow.interrupt()
```

## Status Transitions

```
pending → suspend() → suspended → resume() → pending
pending → interrupt() → interrupted → resume() → pending
active → interrupt() → interrupted  → resume() → active (may be inconsistent)
active → suspend() → suspended  → resume() → active (may be inconsistent)
```

## TTL (Time-To-Live)

<div style="background: linear-gradient(135deg, #7c4dff 0%, #b388ff 100%); color: white; padding: 16px 20px; border-radius: 8px; margin-bottom: 20px;">
  <strong style="font-size: 1.1em;">🧪 Beta Feature</strong><br>
  <span style="opacity: 0.95;">TTL configuration is currently experimental. The API may change in future releases based on feedback.</span>
</div>

MageFlow stores task signatures in Redis during execution. TTL controls how long these signatures persist — both while active and after completion.

By default:

- **Active signatures** expire after **24 hours**
- **Completed signatures** are cleaned up after **5 minutes**

### Configuring TTL

Pass a `MageflowConfig` with a `TTLConfig` to the `Mageflow()` constructor:

```python
from mageflow import Mageflow, MageflowConfig, TTLConfig

hatchet = Mageflow(
    hatchet_client,
    redis_client=redis_client,
    config=MageflowConfig(
        ttl=TTLConfig(
            active_ttl=12 * 60 * 60,  # 12 hours
            done_ttl=10 * 60,          # 10 minutes
        )
    ),
)
```

`active_ttl` sets the Redis TTL on signatures while they're running. `done_ttl` sets the TTL after a signature completes (success or failure). Both values are in **seconds**.

### Per-Signature-Type TTL

Override TTL for specific signature types — tasks, chains, or swarms — using `SignatureTTLConfig`:

```python
from mageflow import Mageflow, MageflowConfig, TTLConfig, SignatureTTLConfig

config = MageflowConfig(
    ttl=TTLConfig(
        active_ttl=24 * 60 * 60,  # general default
        done_ttl=5 * 60,
        task=SignatureTTLConfig(
            active_ttl=6 * 60 * 60,       # tasks expire after 6h
            ttl_when_sign_done=60,         # cleaned up after 1 minute
        ),
        swarm=SignatureTTLConfig(
            active_ttl=48 * 60 * 60,      # swarms get 48h
            ttl_when_sign_done=15 * 60,   # cleaned up after 15 minutes
        ),
    )
)

hatchet = Mageflow(hatchet_client, redis_client=redis_client, config=config)
```

Per-type settings override the general defaults. If a per-type field is `None`, the general value is used.

### Defaults

| Setting | Default |
|---------|---------|
| `active_ttl` | 24 hours (86400s) |
| `done_ttl` | 5 minutes (300s) |
| Per-type `active_ttl` | `None` (uses general) |
| Per-type `ttl_when_sign_done` | `None` (uses general) |

## Examples

### Graceful Workflow Pause and Resume

```python
import mageflow
import asyncio


async def pausable_workflow():
    tasks = [long_task_1, long_task_2, long_task_3]
    workflow = await mageflow.achain(tasks, name="pausable-pipeline")

    await workflow.aio_run_no_wait(StartMessage())

    await asyncio.sleep(10)
    await workflow.suspend()
    print("Workflow paused")

    await asyncio.sleep(30)
    await workflow.resume()
    print("Workflow resumed")
```
