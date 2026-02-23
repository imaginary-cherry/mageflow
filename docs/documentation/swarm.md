# Task Swarms

Task swarms in MageFlow provide a powerful way to run multiple tasks in parallel with controlled concurrency. Unlike chains where tasks run sequentially, swarms allow you to manage a group of tasks that execute simultaneously while controlling how many can run at once and when to trigger callbacks for the entire group.

## What is a Swarm?

A swarm is a collection of tasks that execute in parallel, where:
- Multiple tasks run concurrently with configurable limits
- Tasks can be added dynamically to the swarm queue
- Callbacks are triggered when all tasks complete or when failure conditions are met
- The swarm manages the lifecycle and concurrency of all its component tasks

## Creating a Swarm

Use `mageflow.aswarm()` to create a task swarm:

```python
import mageflow

swarm_signature = await mageflow.aswarm(tasks=[task1, task2, task3])

swarm_signature = await mageflow.aswarm(
    tasks=[process_file1, process_file2, process_file3],
    success_callbacks=[completion_callback],
    error_callbacks=[error_handler],
    config=SwarmConfig(max_concurrency=2),
)
```

!!! info "Alternative Client Usage"
    You can also create swarms using the mageflow client instead of the global `mageflow` module:

    ```python
    from mageflow import Mageflow

    hatchet = Mageflow(hatchet, redis)

    swarm_signature = await hatchet.aswarm(tasks=[task1, task2, task3])
    ```

### Parameters

- `tasks`: List of task signatures, task functions, or task names to run in parallel
- `success_callbacks`: Tasks to execute when all tasks complete successfully
- `error_callbacks`: Tasks to execute when failure conditions are met
- `config`: SwarmConfig object to control swarm behavior
- `is_swarm_closed`: Whether the swarm should be closed immediately (defaults to False)


## Managing Swarm Lifecycle

### Starting a Swarm
Start a swarm like any other task with the `aio_run_no_wait` method:
```python
swarm = await mageflow.aswarm(tasks=[initial_task])
await swarm.aio_run_no_wait(message)
```
All tasks in the swarm will receive the message once they get a task slot to run (the number of slots can be configured with the `max_concurrency` parameter in `SwarmConfig`).


### Adding Tasks

Use `aio_run_in_swarm()` to add and schedule a task in one step:

```python
swarm = await mageflow.aswarm(tasks=[initial_task])
await swarm.aio_run_no_wait(SwarmMessage(swarm_data="shared"))

await swarm.aio_run_in_swarm(additional_task, TaskMessage(data="task-specific"))
```

The task receives its own message data merged with the swarm's shared parameters.
Configure the message model to ignore extra fields so the merge doesn't affect the task:

```python
class NewTaskMessage(BaseModel):
    data: str
    model_config = ConfigDict(extra="ignore")

class SwarmMessage(BaseModel):
    swarm_data: str

@hatchet.task()
async def new_task(message: NewTaskMessage):
    print(message.data)

swarm = await mageflow.aswarm(tasks=[initial_task])
await swarm.aio_run_no_wait(SwarmMessage(swarm_data="swarm_data"))

await swarm.aio_run_in_swarm(new_task, NewTaskMessage(data="hello"))
```

### Closing a Swarm
When you're done adding tasks to the swarm, close it.

```python
await swarm.close_swarm()

# Or create a pre-closed swarm
swarm = await mageflow.aswarm(
    tasks=task_list,
    is_swarm_closed=True
)
```
Once the swarm is closed, it will not accept new tasks and will trigger completion callbacks when all tasks complete.

## Concurrency Control

Swarms automatically manage task concurrency:

```python
file_tasks = [
    await mageflow.asign("process-file", file_path=f"file_{i}.txt")
    for i in range(20)
]

swarm = await mageflow.aswarm(
    tasks=file_tasks,
    config=SwarmConfig(max_concurrency=5),
    is_swarm_closed=True
)

# Only 5 tasks run simultaneously
# As each completes, the next queued task starts
await swarm.aio_run_no_wait(ProcessMessage())
```

This is especially useful when you want to manage a sudden peak in tasks without deploying new workers to support the load.

## Failure Handling

Control how swarms handle task failures:

```python
# Stop after 3 failures
swarm = await mageflow.aswarm(
    tasks=risky_tasks,
    error_callbacks=[handle_swarm_failure],
    config=SwarmConfig(stop_after_n_failures=3)
)

# Continue despite individual failures (no stop limit)
swarm = await mageflow.aswarm(
    tasks=optional_tasks,
    success_callbacks=[process_results],
    config=SwarmConfig(stop_after_n_failures=None)
)
```

## Swarm Callback
The swarm triggers callbacks when all tasks complete. The callback receives a list of all the task results (see [ReturnValue Annotation](callbacks.md#setting-success-callbacks) docs).

## Example Use Cases

### Parallel File Processing

```python
file_paths = ["file1.csv", "file2.csv", "file3.csv"]
process_tasks = [
    await mageflow.asign("process-csv-file", file_path=path)
    for path in file_paths
]

consolidate_results = await mageflow.asign("consolidate-results")
handle_processing_errors = await mageflow.asign("handle-file-errors")

file_swarm = await mageflow.aswarm(
    tasks=process_tasks,
    success_callbacks=[consolidate_results],
    error_callbacks=[handle_processing_errors],
    config=SwarmConfig(max_concurrency=3),
    is_swarm_closed=True
)

await file_swarm.aio_run_no_wait(ProcessingMessage())
```

### Dynamic Task Queue

```python
initial_tasks = [await mageflow.asign("initial-task")]
notification_task = await mageflow.asign("notify-completion")

swarm = await mageflow.aswarm(
    tasks=initial_tasks,
    success_callbacks=[notification_task],
    config=SwarmConfig(max_concurrency=10)
)

await swarm.aio_run_no_wait(InitialMessage())

for data_item in dynamic_data_stream:
    await swarm.aio_run_in_swarm("process-item", ProcessMessage(data=data_item))

await swarm.close_swarm()
```

### Batch Processing with Error Tolerance

```python
batch_tasks = [
    await mageflow.asign("process-record", record_id=i)
    for i in range(1000)
]

completion_report = await mageflow.asign("generate-completion-report")
failure_alert = await mageflow.asign("send-failure-alert")

batch_swarm = await mageflow.aswarm(
    tasks=batch_tasks,
    success_callbacks=[completion_report],
    error_callbacks=[failure_alert],
    config=SwarmConfig(
        max_concurrency=20,
        stop_after_n_failures=50
    ),
    is_swarm_closed=True
)

await batch_swarm.aio_run_no_wait(BatchMessage())
```
