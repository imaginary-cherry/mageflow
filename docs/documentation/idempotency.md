# Idempotency

<div style="background: linear-gradient(135deg, #7c4dff 0%, #b388ff 100%); color: white; padding: 16px 20px; border-radius: 8px; margin-bottom: 20px;">
  <strong style="font-size: 1.1em;">🧪 Beta Feature</strong><br>
  <span style="opacity: 0.95;">Signature retry cache is currently experimental. The API may change in future releases based on feedback.</span>
</div>

Idempotency means that running the same operation multiple times produces the same result as running it once. In distributed systems, tasks can fail and retry at any point — network errors, crashes, timeouts. If retrying a task causes side effects to repeat, you end up with duplicate work and inconsistent state.

## The Problem

When a durable task retries, MageFlow re-executes the task function from the top. Every call to `asign()`, `achain()`, or `aswarm()` creates a new signature in Redis. On a retry, this means:

- **Duplicate signatures** — a second set of signatures is created alongside the originals
- **Orphaned state** — the original signatures from the failed attempt remain in Redis with no task tracking them
- **Double execution** — callbacks and downstream tasks may trigger twice, once for each set of signatures

## The Solution

MageFlow solves this with a **signature retry cache**. On the first execution, every signature created inside a durable task is recorded. On subsequent retries, the cached signatures are returned instead of creating new ones.

## How It Works

```
First run (attempt 1):
  sign("task-a")  → creates TaskSignature, caches it
  chain([a, b])   → creates ChainTaskSignature, caches it

Retry (attempt 2+):
  sign("task-a")  → returns cached TaskSignature
  chain([a, b])   → returns cached ChainTaskSignature
```

The cache is keyed by workflow ID and stored in Redis with a 24-hour TTL. It is automatically cleaned up when the task finishes — either on success or on final failure (no more retries).

## Automatic for Durable Tasks

Idempotency is enabled automatically for all durable tasks. No configuration needed.

```python
@hatchet.durable_task()
async def my_task(msg):
    # These calls are automatically idempotent on retries
    sig_a = await mageflow.asign("task-a", data="hello")
    sig_b = await mageflow.asign("task-b", data="world")

    workflow = await mageflow.achain([sig_a, sig_b])
    return await workflow.aio_run(msg)
```

Regular (non-durable) tasks do **not** use the retry cache.

## Signature Order Matters

The cache replays signatures in the same order they were created. If your task creates signatures conditionally or in a different order on retry, the cache will return the wrong signature.

!!! warning "Keep signature creation deterministic"
    Always create signatures in the same order across retries. Avoid branching logic that changes which signatures are created or their order.

```python
# Good — deterministic order
@hatchet.durable_task()
async def good_task(msg):
    a = await mageflow.asign("task-a")
    b = await mageflow.asign("task-b")
    return await mageflow.achain([a, b])

# Bad — order depends on external state
@hatchet.durable_task()
async def bad_task(msg):
    if await some_external_check():
        a = await mageflow.asign("task-a")
    b = await mageflow.asign("task-b")
```
