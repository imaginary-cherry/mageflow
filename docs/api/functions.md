# Functions API Reference

This page provides an overview of all public functions available from the `mageflow` module.

```python
import mageflow
```

## Task Creation

### `mageflow.asign(task, **options)`

Create a new task signature. See [Signature API Reference](signature.md) for full details.

```python
signature = await mageflow.asign("process-data")
signature = await mageflow.asign(my_task_function, priority="high")
```

### `mageflow.achain(tasks, name, error, success)`

Create a task chain for sequential execution. See [Chain API Reference](chain.md) for full details.

```python
chain = await mageflow.achain(
    tasks=[extract, transform, load],
    name="etl-pipeline",
    success=audit_task,
)
```

### `mageflow.aswarm(tasks, task_name, **options)`

Create a task swarm for parallel execution. See [Swarm API Reference](swarm.md) for full details.

```python
swarm = await mageflow.aswarm(
    tasks=file_tasks,
    task_name="file-processing",
    is_swarm_closed=True,
)
```

## Task Lifecycle

### `mageflow.resume(key)`

Resume a suspended task by its key.

```python
async def resume(key: RapyerKey)
```

**Parameters:**

- `key` (RapyerKey): The key identifying the task signature to resume

```python
await mageflow.resume(task_key)
```

### `mageflow.pause(key)`

Pause a running task by its key.

```python
async def pause(key: RapyerKey)
```

**Parameters:**

- `key` (RapyerKey): The key identifying the task signature to pause

```python
await mageflow.pause(task_key)
```

### `mageflow.remove(key)`

Remove a task signature by its key.

```python
async def remove(key: RapyerKey)
```

**Parameters:**

- `key` (RapyerKey): The key identifying the task signature to remove

```python
await mageflow.remove(task_key)
```

### `mageflow.lock_task(key)`

Create a lock on a task signature. While locked, the signature cannot be deleted or change status.

```python
def lock_task(key: RapyerKey, **kwargs)
```

**Parameters:**

- `key` (RapyerKey): The key identifying the task signature to lock

```python
async with mageflow.lock_task(task_key) as locked_signature:
    # signature is locked for the duration of this block
    ...
```

!!! warning
    This function can be dangerous as signatures won't be able to be deleted or change status while locked. It may prevent a task from finishing, causing a timeout.

## Loading Signatures

### `mageflow.load_signature(key)`

Load a stored signature from Redis by its key.

```python
async def load_signature(key: RapyerKey) -> Optional[Signature]
```

**Parameters:**

- `key` (RapyerKey): The key identifying the signature to load

```python
signature = await mageflow.load_signature(task_key)
```

## Atomic Operations

### `mageflow.abounded_field(model)`

Context manager for performing multiple signature updates as a single atomic Redis transaction. When entering the context, the model is loaded to its current state. All changes made within the context are saved together when the context exits.

```python
async with mageflow.abounded_field():
    # All updates here are batched into a single transaction
    ...
```

## Configuration

See [Configuration API Reference](config.md) for full details on `MageflowConfig`, `TTLConfig`, `SignatureTTLConfig`, `AcceptParams`, and `SwarmConfig`.
