# Swarm API Reference

This page provides detailed API documentation for swarm functionality in MageFlow.

## mageflow.swarm()

Create a new task swarm for parallel execution.

```python
async def swarm(
    tasks: List[TaskSignatureConvertible],
    success_callbacks: Optional[List[TaskSignatureConvertible]] = None,
    error_callbacks: Optional[List[TaskSignatureConvertible]] = None,
    config: SwarmConfig = SwarmConfig(),
    task_name: Optional[str] = None,
    is_swarm_closed: bool = False,
    **kwargs
) -> SwarmTaskSignature
```

**Parameters:**
- `tasks`: List of tasks to run in parallel
- `success_callbacks`: Tasks executed when all tasks complete successfully
- `error_callbacks`: Tasks executed when failure conditions are met
- `config`: Configuration object controlling swarm behavior
- `task_name`: Optional name for the swarm
- `is_swarm_closed`: Whether to close swarm immediately (prevents adding new tasks)
- `**kwargs`: Additional parameters passed to task contexts

**Returns:** `SwarmTaskSignature` - The swarm task signature

## SwarmConfig

Configuration class for controlling swarm behavior.

```python
class SwarmConfig(BaseModel):
    max_concurrency: int = 30
    stop_after_n_failures: Optional[int] = None
    max_task_allowed: Optional[int] = None
```

**Fields:**
- `max_concurrency`: Maximum number of tasks running simultaneously (default: 30)
- `stop_after_n_failures`: Stop swarm after N task failures (default: None - no limit)
- `max_task_allowed`: Maximum total tasks allowed in swarm (default: None - no limit)

## SwarmTaskSignature

The main swarm class that manages parallel task execution.

### Properties

- `tasks`: List of all task IDs in the swarm
- `tasks_left_to_run`: Queue of tasks waiting to execute
- `finished_tasks`: List of successfully completed task IDs
- `failed_tasks`: List of failed task IDs
- `current_running_tasks`: Number of currently executing tasks
- `is_swarm_closed`: Whether new tasks can be added
- `config`: SwarmConfig instance

### Methods

#### aio_run_no_wait()

Start the swarm execution.

```python
async def aio_run_no_wait(self, msg: BaseModel, **kwargs)
```

**Parameters:**
- `msg`: Message object to pass to tasks

#### aio_run_in_swarm()

Add a task to the swarm and immediately schedule it for execution.

```python
async def aio_run_in_swarm(
    self,
    task: TaskSignatureConvertible,
    msg: BaseModel,
    close_on_max_task: bool = True,
)
```

**Parameters:**
- `task`: Task signature, function, or task name to add and run
- `msg`: Message object with data specific to this task
- `close_on_max_task`: Automatically close the swarm when `max_task_allowed` is reached (default: `True`)

**Raises:**
- `TooManyTasksError`: If `max_task_allowed` limit exceeded
- `SwarmIsCanceledError`: If swarm is canceled

#### close_swarm()

Close the swarm to prevent new tasks and trigger completion callbacks.

```python
async def close_swarm() -> SwarmTaskSignature
```

**Returns:** The swarm instance

#### is_swarm_done()

Check if swarm has completed all tasks.

```python
async def is_swarm_done() -> bool
```

**Returns:** `True` if swarm is closed and all tasks finished

## Error Classes

### TooManyTasksError

Raised when attempting to add tasks beyond `max_task_allowed` limit.

### SwarmIsCanceledError

Raised when attempting to add tasks to a canceled swarm.
