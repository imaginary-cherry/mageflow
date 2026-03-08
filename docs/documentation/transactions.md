# Transactions

MageFlow transactions let you group multiple signature changes into a single operation. 
All changes within a transaction either succeed together or fail together, ensuring your data stays consistent, and saving in IO operation.

## Why Transactions?

When you update multiple fields or signatures, each change is normally saved to Redis individually. This can lead to problems:

- A task might be published before its parameters are fully configured
- Partial updates could leave signatures in an inconsistent state
- Other workers might read intermediate states between updates
- Multiple IO operation can slow your flow and might even cause a timeout.

Transactions solve this by batching all changes into a single Redis pipeline that executes atomically.

## Using `abounded_field`

The `abounded_field` context manager is the primary way to create transactions in MageFlow.

### Basic Usage

```python
import mageflow


async with mageflow.abounded_field():
    signature = await mageflow.asign("process-data")
    signature.kwargs["input"] = "new-value"
    signature.kwargs["priority"] = "high"
    # Both updates are saved together when the context exits
```

### Updating Multiple Signatures

You can update multiple signatures in a single transaction:

```python
async with mageflow.abounded_field():
    task_a = await mageflow.asign("task-a")
    task_b = await mageflow.asign("task-b")

    task_a.kwargs["shared_ref"] = "batch-123"
    task_b.kwargs["shared_ref"] = "batch-123"
    task_a.kwargs["role"] = "producer"
    task_b.kwargs["role"] = "consumer"
```

```python
async with mageflow.abounded_field(ignore_redis_error=True):
    signature.kwargs["optional_field"] = "value"
```

## Bulk Swarm Operations

MageFlow provides helper methods on swarm signatures that use `abounded_field` internally. These are convenient shortcuts for common patterns where you need to add tasks and set their parameters atomically.

### `aio_run_in_swarm` — Shared Message

Add one or more tasks to a swarm where all tasks receive the same message:

```python
swarm = await mageflow.aswarm(tasks=[initial_task])
await swarm.aio_run_no_wait(SwarmMessage(swarm_data="shared"))

# Single task
await swarm.aio_run_in_swarm(new_task, TaskMessage(data="hello"))

# Multiple tasks with the same message
tasks = await template_task.aduplicate_many(5)
await swarm.aio_run_in_swarm(tasks, TaskMessage(data="hello"))
```

Each task's message is merged with the swarm's shared kwargs. Internally, this adds the tasks and sets their parameters inside an `abounded_field` transaction.

### `aio_run_tasks_in_swarm` — Individual Messages

Add multiple tasks where each receives its own message:

```python
tasks = [task_a, task_b, task_c]
messages = [
    TaskMessage(data="for-a"),
    TaskMessage(data="for-b"),
    TaskMessage(data="for-c"),
]

await swarm.aio_run_tasks_in_swarm(tasks, messages)
```

The `tasks` and `msgs` lists must have the same length. Like `aio_run_in_swarm`, this uses `abounded_field` internally to ensure all tasks are added and configured atomically.