# Signature API Reference

This page provides detailed API documentation for task signature functionality in MageFlow.

## `mageflow.asign(task, **options)`

Create a new task signature.

```python
async def asign(task: str | HatchetTaskType, **options: Any) -> TaskSignature
```

**Parameters:**
- `task` (str | HatchetTaskType): Task name (string) or HatchetTask instance to create signature for
- `**options`: Additional signature options including:
  - `kwargs`: Dictionary of task parameters
  - `creation_time`: Timestamp when signature was created
  - `model_validators`: Validation models for task input
  - `success_callbacks`: List of task IDs to execute on success
  - `error_callbacks`: List of task IDs to execute on error
  - `task_status`: Initial status for the task

**Example:**
```python
signature = await mageflow.asign("process-order", priority="high")
```

## TaskSignature

The main signature class that manages task execution and lifecycle.

### Properties

- `task_name`: Name of the task
- `kwargs`: Dictionary of task parameters
- `creation_time`: When the signature was created
- `success_callbacks`: Tasks executed when task completes successfully
- `error_callbacks`: Tasks executed when task fails
- `task_status`: Current status information
- `key`: Unique identifier for the signature

### Class Methods

#### `delete_signature(task_id)`

Delete a signature by ID.

```python
@classmethod
async def delete_signature(cls, task_id: TaskIdentifierType)
```

### Instance Methods

#### `aio_run_no_wait(msg)`

Execute the task asynchronously without waiting for completion.

```python
async def aio_run_no_wait(self, msg: BaseModel)
```

**Parameters:**
- `msg` (BaseModel): Message object to pass to the task

#### `remove(with_error, with_success)`

Remove the signature and optionally its callbacks.

```python
async def remove(self, with_error: bool = True, with_success: bool = True)
```

### Lifecycle Management

#### `suspend()`

Suspend task execution before it starts.

```python
async def suspend()
```

Sets task status to `SUSPENDED`. The task will not execute until resumed.

#### `resume()`

Resume a suspended task.

```python
async def resume()
```

Restores the previous status and re-triggers execution if needed.

#### `interrupt()`

Aggressively interrupt task execution.

```python
async def interrupt()
```

#### `pause_task(pause_type)`

Pause task with specified action type.

```python
async def pause_task(self, pause_type: PauseActionTypes = PauseActionTypes.SUSPEND)
```

**Parameters:**
- `pause_type` (PauseActionTypes): Either `SUSPEND` or `INTERRUPT`

## Helper Functions

### `mageflow.load_signature(key)`

Load stored signature by ID from redis.

```python
async def load_signature(key) -> Optional[Signature]
```

### `mageflow.resume_task(task_id)` / `mageflow.resume(task_id)`

```python
async def resume_task(task_id)
async def resume(task_id)  # Same as resume_task
```

### `mageflow.pause(task_id)`

```python
async def pause(task_id)
```

### `mageflow.remove(task_id)`

```python
async def remove(task_id)
```

### `mageflow.lock_task(task_id)`

```python
def lock_task(task_id, **kwargs)
```

Create a lock of the task signature, the signature will not be deleted nor change status while locked.
!!! warning
    This function can be dangerous as signatures wont be able to be deleted or change status while locked. It may prevent task from finishing, causing timeout.
