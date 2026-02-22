# Setup

This guide walks through setting up MageFlow with your preferred task manager backend and configuring the necessary dependencies.

## Installation

Install MageFlow with your preferred task manager backend using the appropriate extra:

### Hatchet Backend
```bash
pip install mageflow[hatchet]
```

## Configuration

MageFlow requires configuration for both the task manager backend and Redis storage.

### Basic Setup with Hatchet

```python
import redis
from hatchet_sdk import Hatchet, ClientConfig

import mageflow

config_obj = ClientConfig(token="your-hatchet-token")

redis_client = redis.asyncio.from_url(
    "redis-url",
    max_connections=1028,
    decode_responses=True,
)

hatchet = Hatchet(debug=True, config=config_obj)

# Create the MageFlow instance
hatchet = mageflow.Mageflow(hatchet, redis_client=redis_client)
```

For a smooth transition experience, we recommend calling the wrapped object with the original name, it has all the same functions and configurations.

## Creating and Registering Tasks

### Task Definition

Define tasks using the mageflow task decorators:

```python
@hatchet.task(name="process-data", input_validator=YourModelA)
async def process_data(msg: YourModelA):
    result = {"processed": msg.data}
    return result

@hatchet.task(name="send-notification", input_validator=YourModelB)
async def send_notification(msg: YourModelB):
    print(f"Notification sent for: {msg.data}")
    return {"status": "sent"}
```

### Durable Tasks

For long-running or critical tasks, use durable tasks:

```python
@hatchet.durable_task(name="critical-process", input_validator=YourModelB)
async def critical_process(msg):
    await asyncio.sleep(5)
    return {"completed": True}
```

### Backpropagation
If you want the task to stay with the hatchet definition (with ctx parameter), use the `param_config` parameter:

```python
hatchet = mageflow.Mageflow(hatchet, redis_client=redis_client, param_config=AcceptParams.ALL)

@hatchet.task(name="send-notification", input_validator=YourModelB)
async def send_notification(msg: YourModelB, ctx: Context):
    print(f"Notification sent for: {msg.data}")
    return {"status": "sent"}
```

### Using with_ctx and with_signature Decorators

MageFlow provides two special decorators that allow you to override the default behavior on a per-task basis:

#### with_ctx

The `with_ctx` decorator allows a specific task to receive the Hatchet context even when the client is configured with `NO_CTX`. This is useful when most of your tasks don't need the context, but specific tasks do:

```python
hatchet = mageflow.Mageflow(hatchet, redis_client=redis_client, param_config=AcceptParams.NO_CTX)

@hatchet.task(name="context-aware-task", input_validator=YourModel)
@hatchet.with_ctx
async def context_aware_task(msg: YourModel, ctx: Context):
    step_id = ctx.step_run_id
    print(f"Running in step: {step_id}")
    return {"processed": True}

@hatchet.task(name="regular-task", input_validator=YourModel)
async def regular_task(msg: YourModel):
    return {"processed": True}
```

#### with_signature

The `with_signature` decorator allows a task to receive its own task signature as a parameter. This is useful when a task needs to inspect or manipulate its own execution configuration:

```python
from thirdmagic.task import TaskSignature

@hatchet.task(name="self-aware-task", input_validator=YourModel)
@hatchet.with_signature
async def self_aware_task(msg: YourModel, signature: TaskSignature):
    task_name = signature.task_name
    task_id = signature.key
    print(f"Running task: {task_name} with ID: {task_id}")
    return {"task_name": task_name}

# Combine both decorators
@hatchet.task(name="full-access-task", input_validator=YourModel)
@hatchet.with_ctx
@hatchet.with_signature
async def full_access_task(msg: YourModel, ctx: Context, signature: TaskSignature):
    step_id = ctx.step_run_id
    task_name = signature.task_name
    return {"step_id": step_id, "task_name": task_name}
```

## Worker Setup

Create a worker to run your registered tasks:

```python
def main():
    workflows = [
        process_data,
        send_notification,
        critical_process,
    ]

    worker = hatchet.worker("my-worker", workflows=workflows)
    worker.start()

if __name__ == "__main__":
    main()
```

## Next Steps

With your setup complete, you're ready to:

1. **Define workflows** using [callbacks](documentation/callbacks.md)
2. **Chain tasks** together with [task chains](documentation/chain.md)
3. **Run parallel tasks** using [swarms](documentation/swarm.md)
4. **Monitor and debug** your workflows using the built-in tools
