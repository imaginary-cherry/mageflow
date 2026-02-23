# Chain API Reference

This page provides detailed API documentation for chain functionality in MageFlow.

## `mageflow.achain(tasks, name, error, success)`

Create a new task chain for sequential execution.

```python
async def achain(
    tasks: List[TaskSignatureConvertible],
    name: Optional[str] = None,
    error: Optional[TaskInputType] = None,
    success: Optional[TaskInputType] = None,
) -> ChainTaskSignature
```

**Parameters:**
- `tasks` (list): List of tasks to execute sequentially (minimum 2 tasks required)
- `name` (str): Optional name for the chain (defaults to first task's name)
- `error` (TaskInputType): Task to execute when any task in the chain fails
- `success` (TaskInputType): Task to execute when all tasks complete successfully

**Example:**
```python
chain = await mageflow.achain(
    tasks=[extract, transform, load],
    name="etl-pipeline",
    success=audit_task,
    error=alert_task
)
```

## ChainTaskSignature

The main chain class that manages sequential task execution.

### Properties

- `tasks`: List of task IDs in the chain sequence
- `task_name`: Name of the chain (derived from first task if not specified)
- `success_callbacks`: Tasks executed when chain completes successfully
- `error_callbacks`: Tasks executed when any task fails

### Methods

#### `aio_run_no_wait(msg)`

Start the chain execution.

```python
await chain.aio_run_no_wait(InputMessage(data="start"))
```

#### `suspend()`

Suspend the entire chain and all its tasks.

```python
async def suspend()
```

Suspends all tasks in the chain and sets the chain status to `SUSPENDED`.

#### `resume()`

Resume the chain and all its tasks.

```python
async def resume()
```

Resumes all tasks in the chain and restores the previous status.

#### `interrupt()`

Interrupt the chain and all its tasks.

```python
async def interrupt()
```

Interrupts all tasks in the chain and sets the status to `INTERRUPTED`.
