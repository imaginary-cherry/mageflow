# Swarm API Reference

This page provides detailed API documentation for swarm functionality in MageFlow.

## `mageflow.aswarm(tasks, task_name, **options)`

Create a new task swarm for parallel execution.

```python
async def aswarm(
    tasks: List[TaskSignatureConvertible],
    task_name: Optional[str] = None,
    success_callbacks: Optional[List[TaskSignatureConvertible]] = None,
    error_callbacks: Optional[List[TaskSignatureConvertible]] = None,
    config: SwarmConfig = SwarmConfig(),
    is_swarm_closed: bool = False,
    **kwargs
) -> SwarmTaskSignature
```

**Parameters:**
- `tasks` (list): List of tasks to run in parallel
- `task_name` (str): Optional name for the swarm
- `success_callbacks` (list): Tasks executed when all tasks complete successfully
- `error_callbacks` (list): Tasks executed when failure conditions are met
- `config` (SwarmConfig): Configuration object controlling swarm behavior
- `is_swarm_closed` (bool): Whether to close swarm immediately (prevents adding new tasks)

**Example:**
```python
swarm = await mageflow.aswarm(
    tasks=file_tasks,
    task_name="file-processing",
    config=SwarmConfig(max_concurrency=5),
    is_swarm_closed=True
)
```

## SwarmConfig

Configuration class for controlling swarm behavior.

```python
class SwarmConfig(BaseModel):
    max_concurrency: int = 30
    stop_after_n_failures: Optional[int] = None
    max_task_allowed: Optional[int] = None
```

**Fields:**
- `max_concurrency` (int): Maximum number of tasks running simultaneously (default: 30)
- `stop_after_n_failures` (int): Stop swarm after N task failures (default: None - no limit)
- `max_task_allowed` (int): Maximum total tasks allowed in swarm (default: None - no limit)

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

#### `aio_run_no_wait(msg)`

Start the swarm execution.

```python
async def aio_run_no_wait(self, msg: BaseModel)
```

**Parameters:**
- `msg` (BaseModel): Message object to pass to tasks

#### `aio_run_in_swarm(task, msg, close_on_max_task)`

Add one or more tasks to the swarm and immediately schedule them. All tasks receive the same message.

```python
async def aio_run_in_swarm(
    self,
    task: TaskSignatureConvertible | list[TaskSignatureConvertible],
    msg: BaseModel,
    options: TriggerWorkflowOptions = None,
    close_on_max_task: bool = True,
)
```

**Parameters:**
- `task`: A single task or a list of tasks to add and run
- `msg` (BaseModel): Message object shared across all tasks
- `options` (TriggerWorkflowOptions): Optional Hatchet trigger options
- `close_on_max_task` (bool): Automatically close the swarm when `max_task_allowed` is reached (default: `True`)

#### `close_swarm()`

Close the swarm to prevent new tasks and trigger completion callbacks.

```python
async def close_swarm() -> SwarmTaskSignature
```

#### `is_swarm_done()`

Check if swarm has completed all tasks.

```python
async def is_swarm_done() -> bool
```

## Error Classes

### TooManyTasksError

Raised when attempting to add tasks beyond `max_task_allowed` limit.

### SwarmIsCanceledError

Raised when attempting to add tasks to a canceled swarm.
