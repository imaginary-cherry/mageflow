# Configuration API Reference

This page provides detailed API documentation for MageFlow configuration classes.

```python
from mageflow import MageflowConfig, TTLConfig, SignatureTTLConfig
from mageflow.callbacks import AcceptParams
```

## MageflowConfig

Top-level configuration for MageFlow. Passed to the [`Mageflow` client](client.md) or to [`start_mageflow`](functions.md#mageflowstart_mageflowredis-config).

```python
@dataclass
class MageflowConfig:
    ttl: TTLConfig = TTLConfig()
    param_config: AcceptParams = AcceptParams.NO_CTX
    use_idempotency: bool = True
```

**Fields:**

- `ttl` ([TTLConfig](#ttlconfig)): TTL settings for signatures
- `param_config` ([AcceptParams](#acceptparams)): Default parameter mode for task callbacks
- `use_idempotency` (bool): Enable the [signature retry cache](../documentation/idempotency.md) for durable tasks (default: `True`). Set to `False` to disable idempotency globally.

**Example:**

```python
from mageflow import Mageflow, MageflowConfig, TTLConfig
from mageflow.callbacks import AcceptParams

config = MageflowConfig(
    ttl=TTLConfig(active_ttl=3600),
    param_config=AcceptParams.NO_CTX,
    use_idempotency=False,  # disable retry cache for durable tasks
)

client = Mageflow(
    hatchet_client=hatchet,
    redis_client="redis://localhost:6379",
    config=config,
)
```

## AcceptParams

Enum that controls which parameters a task function receives when invoked by MageFlow.

```python
from mageflow.callbacks import AcceptParams

class AcceptParams(Enum):
    JUST_MESSAGE = 1
    NO_CTX = 2
    ALL = 3
```

**Values:**

- `JUST_MESSAGE` — The task receives only the message
- `NO_CTX` — The task receives the message and extra kwargs, but not the Hatchet context
- `ALL` — The task receives the message, the Hatchet context, and extra kwargs

**Example:**

```python
# Task receives only the message
@client.task(name="simple-task")
async def simple(msg: MyMessage):
    ...

# Task receives message + Hatchet context (use with_ctx decorator or AcceptParams.ALL)
@client.task(name="context-task")
@client.with_ctx
async def with_context(msg: MyMessage, ctx: Context):
    ...
```

## TTLConfig

Controls time-to-live for different signature types. TTL determines how long signatures persist in Redis.

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

- `active_ttl` (int): General TTL in seconds for active signatures (default: 24 hours). Applies to all signature types unless overridden.
- `ttl_when_sign_done` (int): TTL in seconds after a signature completes (default: 5 minutes). Controls how long completed signatures remain in Redis before cleanup.
- `task` ([SignatureTTLConfig](#signaturettlconfig)): Override TTL specifically for task signatures
- `chain` ([SignatureTTLConfig](#signaturettlconfig)): Override TTL specifically for chain signatures
- `swarm` ([SignatureTTLConfig](#signaturettlconfig)): Override TTL specifically for swarm signatures

**Example:**

```python
from mageflow import TTLConfig, SignatureTTLConfig

ttl = TTLConfig(
    active_ttl=12 * 60 * 60,       # 12 hours general
    ttl_when_sign_done=60,          # 1 minute cleanup
    task=SignatureTTLConfig(
        active_ttl=6 * 60 * 60,    # tasks expire after 6 hours
    ),
    swarm=SignatureTTLConfig(
        active_ttl=48 * 60 * 60,   # swarms live longer (48 hours)
    ),
)
```

### TTL Resolution

Per-signature-type TTL values take priority over the general values. When a per-type value is `None`, the general value is used as fallback:

| Signature Type | Active TTL | Done TTL |
|---|---|---|
| Task | `task.active_ttl` or `active_ttl` | `task.ttl_when_sign_done` or `ttl_when_sign_done` |
| Chain | `chain.active_ttl` or `active_ttl` | `chain.ttl_when_sign_done` or `ttl_when_sign_done` |
| Swarm | `swarm.active_ttl` or `active_ttl` | `swarm.ttl_when_sign_done` or `ttl_when_sign_done` |

## SignatureTTLConfig

Per-signature-type TTL overrides. When set to `None`, the general TTL from [`TTLConfig`](#ttlconfig) is used.

```python
@dataclass
class SignatureTTLConfig:
    active_ttl: Optional[int] = None
    ttl_when_sign_done: Optional[int] = None
```

**Fields:**

- `active_ttl` (int, optional): Override active TTL in seconds for this signature type
- `ttl_when_sign_done` (int, optional): Override done TTL in seconds for this signature type

## SwarmConfig

Configuration for controlling swarm behavior. Passed to [`mageflow.aswarm`](functions.md#mageflowaswarmtasks-task_name-options).

```python
class SwarmConfig(BaseModel):
    max_concurrency: int = 30
    stop_after_n_failures: Optional[int] = None
    max_task_allowed: Optional[int] = None
```

**Fields:**

- `max_concurrency` (int): Maximum number of tasks running simultaneously (default: 30)
- `stop_after_n_failures` (int, optional): Stop the swarm after this many task failures (default: `None` — no limit)
- `max_task_allowed` (int, optional): Maximum total tasks allowed in the swarm (default: `None` — no limit)

**Example:**

```python
from thirdmagic.swarm import SwarmConfig

swarm = await mageflow.aswarm(
    tasks=file_tasks,
    task_name="file-processing",
    config=SwarmConfig(
        max_concurrency=5,
        stop_after_n_failures=3,
        max_task_allowed=100,
    ),
)
```
