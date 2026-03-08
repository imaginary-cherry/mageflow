# Client API Reference

This page provides detailed API documentation for the MageFlow client functionality.

## HatchetMageflow Client

The main MageFlow client that wraps your task manager (Hatchet) and provides enhanced functionality. It acts exactly like the Hatchet client, but with additional features.

### Initialization

```python
from mageflow import Mageflow, MageflowConfig
from mageflow.callbacks import AcceptParams
from hatchet_sdk import Hatchet

client = Mageflow(
    hatchet_client=Hatchet(),
    redis_client="redis://localhost:6379",
    config=MageflowConfig(
        param_config=AcceptParams.NO_CTX,
    ),
)
```

**Parameters:**
- `hatchet_client` (Hatchet): The Hatchet SDK client instance
- `redis_client` (Redis | str): Redis client instance or connection string for state management
- `config` (MageflowConfig): Configuration for param handling, TTL, and other settings. See [TTL](../documentation/task-lifecycle.md#ttl-time-to-live)

### MageflowConfig

```python
@dataclass
class MageflowConfig:
    ttl: TTLConfig
    param_config: AcceptParams = AcceptParams.NO_CTX
```

**Fields:**
- `ttl` (TTLConfig): TTL settings for signatures. See [TTL](../documentation/task-lifecycle.md#ttl-time-to-live)
- `param_config` (AcceptParams): Parameter configuration for context handling (`NO_CTX`, `ALL`, `CTX_ONLY`)

### Client Methods

#### `asign(task, **options)`

Create a task signature.

```python
signature = await client.asign("my-task", priority="high")
signature = await client.asign(my_task_function)
```

#### `achain(tasks, name, error, success)`

Create a task chain.

```python
chain = await client.achain([task1, task2, task3], name="my-chain")
```

#### `aswarm(tasks, task_name, **options)`

Create a task swarm.

```python
swarm = await client.aswarm(tasks=[task1, task2], task_name="my-swarm")
```

#### `with_ctx`

Override the default parameter configuration to enable context for a specific task.

```python
@client.task(name="context-task")
@client.with_ctx
async def my_task(msg: MyModel, ctx: Context):
    return {"status": "completed"}
```

The `with_ctx` decorator overrides the client's default `param_config` setting for a specific task. When applied, the task will receive the Hatchet context parameter even if the client was initialized with `AcceptParams.NO_CTX`.

#### `with_signature`

Enable a task to receive its own TaskSignature as a parameter.

```python
from thirdmagic.task import TaskSignature

@client.task(name="signature-aware-task")
@client.with_signature
async def my_task(msg: MyModel, signature: TaskSignature):
    task_name = signature.task_name
    return {"task_name": task_name}
```

The `with_signature` decorator allows a task to receive its own `TaskSignature` object as a parameter. This provides access to the task's configuration, including its name, identifiers, callbacks, and other metadata.

#### `stagger_execution(wait_delta)`

Randomly delay task execution to prevent resource deadlocks when multiple tasks compete for the same resources.

```python
from datetime import timedelta

@client.task(name="resource-intensive-task")
@client.stagger_execution(wait_delta=timedelta(seconds=10))
async def my_task(msg: MyModel):
    return {"status": "completed"}
```

**Parameters:**
- `wait_delta` (timedelta): Maximum delay time for staggering. The actual delay will be a random value between 0 and `wait_delta`.

The `stagger_execution` decorator adds a random delay between 0 and `wait_delta` seconds before task execution and automatically extends the task timeout by the stagger duration.
