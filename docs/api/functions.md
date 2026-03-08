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

## Configuration Classes

### `MageflowConfig`

Top-level configuration for MageFlow.

```python
@dataclass
class MageflowConfig:
    ttl: TTLConfig = TTLConfig()
    param_config: AcceptParams = AcceptParams.NO_CTX
```

**Fields:**

- `ttl` (TTLConfig): TTL settings for signatures
- `param_config` (AcceptParams): Default parameter mode for task callbacks

### `TTLConfig`

Controls time-to-live for different signature types.

```python
@dataclass
class TTLConfig:
    active_ttl: int = 86400            # 24 hours
    ttl_when_sign_done: int = 300      # 5 minutes
    task: SignatureTTLConfig = SignatureTTLConfig()
    chain: SignatureTTLConfig = SignatureTTLConfig()
    swarm: SignatureTTLConfig = SignatureTTLConfig()
```

**Fields:**

- `active_ttl` (int): General TTL in seconds for active signatures (default: 24 hours)
- `ttl_when_sign_done` (int): TTL in seconds after a signature completes (default: 5 minutes)
- `task` (SignatureTTLConfig): Override TTL for task signatures
- `chain` (SignatureTTLConfig): Override TTL for chain signatures
- `swarm` (SignatureTTLConfig): Override TTL for swarm signatures

### `SignatureTTLConfig`

Per-signature-type TTL overrides. When set to `None`, the general TTL from `TTLConfig` is used.

```python
@dataclass
class SignatureTTLConfig:
    active_ttl: Optional[int] = None
    ttl_when_sign_done: Optional[int] = None
```

**Fields:**

- `active_ttl` (int, optional): Override active TTL for this signature type
- `ttl_when_sign_done` (int, optional): Override done TTL for this signature type
