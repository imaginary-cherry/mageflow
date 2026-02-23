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
