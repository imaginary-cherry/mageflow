# Client API Reference

This page provides detailed API documentation for the MageFlow client functionality.

## HatchetMageflow Client

The main MageFlow client that wraps your task manager (Hatchet) and provides enhanced functionality. It acts exactly like the Hatchet client, but with additional features.

### Initialization

```python
from mageflow import Mageflow
from hatchet_sdk import Hatchet

# Create MageFlow client
client = Mageflow(
    hatchet_client: Hatchet,
    redis_client: Redis | str = None,
    param_config: AcceptParams = AcceptParams.NO_CTX
)
```

**Parameters:**
- `hatchet_client`: The Hatchet SDK client instance
- `redis_client`: Redis client instance or connection string for state management
- `param_config`: Parameter configuration for context handling (NO_CTX, ALL, CTX_ONLY)

### Client Methods

#### with_ctx()

Override the default parameter configuration to enable context for a specific task.

**Usage:**
```python
@client.task(name="context-task")
@client.with_ctx
async def my_task(msg: MyModel, ctx: Context):
# This task receives context even if client has NO_CTX
    return {"status": "completed"}
```

**Description:**
The `with_ctx` decorator overrides the client's default `param_config` setting for a specific task. When applied, the task will receive the Hatchet context parameter even if the client was initialized with `AcceptParams.NO_CTX`. This is useful when most tasks don't need context but specific tasks require access to Hatchet's context object for step management, workflow control, or other context-dependent operations.

#### with_signature()

Enable a task to receive its own TaskSignature as a parameter.


**Usage:**
```python
from mageflow import TaskSignature

@client.task(name="signature-aware-task")
@client.with_signature
async def my_task(msg: MyModel, signature: TaskSignature):
    # Access the task's signature
    task_name = signature.task_name
    task_id = signature.task_identifiers
    return {"task_name": task_name}
```

**Description:**
The `with_signature` decorator allows a task to receive its own `TaskSignature` object as a parameter. This provides access to the task's configuration, including its name, identifiers, callbacks, and other metadata. This is particularly useful for tasks that need to be self-aware or need to inspect their own execution configuration at runtime.
