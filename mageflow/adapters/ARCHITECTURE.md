# Mageflow Task Manager Abstraction Architecture

## Overview

This document describes the architecture for supporting multiple task managers (Hatchet, TaskIQ, etc.) in Mageflow while maintaining a single, clean codebase.

## Key Principles

1. **Single Entry Point**: The `Mageflow()` factory function in `client.py` is the ONLY place where task manager type checking occurs.

2. **Protocol-Based Design**: All task-manager-specific code implements common protocols defined in `adapters/protocols.py`.

3. **Dependency Injection**: The appropriate adapter is injected at initialization time, and all subsequent code uses the adapter interface.

4. **No Scattered If-Checks**: After initialization, there should be zero `if adapter_type == X` checks throughout the codebase.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Code                                │
│                                                                  │
│  mage = Mageflow(hatchet_client=Hatchet())                      │
│  # or                                                            │
│  mage = Mageflow(taskiq_broker=RedisBroker(...))                │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Mageflow Factory                              │
│                     (client.py)                                  │
│                                                                  │
│  - Detects task manager type                                     │
│  - Creates appropriate adapter                                   │
│  - Returns MageflowClient                                        │
│                                                                  │
│  THIS IS THE ONLY PLACE WITH TYPE DETECTION!                    │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MageflowClient                                │
│                                                                  │
│  - Uses TaskManagerAdapter protocol                              │
│  - Task/worker/workflow management                               │
│  - No task-manager-specific code                                 │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                 TaskManagerAdapter Protocol                      │
│                   (adapters/protocols.py)                        │
│                                                                  │
│  - task() / durable_task()                                       │
│  - worker()                                                      │
│  - workflow()                                                    │
│  - extract_execution_info()                                      │
│  - create_task_context()                                         │
│  - create_framework_tasks()                                      │
└───────────────────────────┬─────────────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            │                               │
            ▼                               ▼
┌─────────────────────┐       ┌─────────────────────┐
│   HatchetAdapter    │       │    TaskIQAdapter    │
│                     │       │                     │
│ adapters/hatchet/   │       │ adapters/taskiq/    │
│ - adapter.py        │       │ - adapter.py        │
│ - context.py        │       │ - context.py        │
│ - workflow.py       │       │ - workflow.py       │
│ - framework_tasks.py│       │ - framework_tasks.py│
│ - invoker.py        │       │ - invoker.py        │
└─────────────────────┘       └─────────────────────┘
```

## Protocol Interfaces

### TaskManagerAdapter

The main interface that all task managers must implement:

```python
class TaskManagerAdapter(ABC):
    adapter_type: TaskManagerType

    @abstractmethod
    def task(self, name: str | None = None, **options) -> Callable:
        """Create a task decorator."""

    @abstractmethod
    def durable_task(self, name: str | None = None, **options) -> Callable:
        """Create a durable task decorator."""

    @abstractmethod
    def worker(self, name: str, workflows: list = None, **options) -> WorkerAdapter:
        """Create a worker."""

    @abstractmethod
    def workflow(self, name: str, **options) -> WorkflowAdapter:
        """Create a workflow adapter for triggering tasks."""

    @abstractmethod
    def extract_execution_info(self, raw_context: Any, message: Any) -> TaskExecutionInfo:
        """Extract normalized execution info from native context."""

    @abstractmethod
    def create_task_context(self, raw_context: Any, message: Any) -> TaskContext:
        """Create a TaskContext wrapper for native context."""

    @abstractmethod
    def create_framework_tasks(self) -> list:
        """Create internal framework tasks (chain, swarm)."""
```

### TaskContext

Normalizes the context object that task functions receive:

```python
@runtime_checkable
class TaskContext(Protocol):
    @property
    def execution_info(self) -> TaskExecutionInfo:
        """Get task execution information."""

    def log(self, message: str) -> None:
        """Log a message."""

    async def cancel(self) -> None:
        """Request cancellation."""

    def refresh_timeout(self, duration: timedelta) -> None:
        """Extend timeout."""
```

### TaskExecutionInfo

Task-manager-agnostic execution metadata:

```python
@dataclass
class TaskExecutionInfo:
    task_data: dict       # Mageflow metadata (signature key, etc.)
    workflow_id: str      # Execution ID
    task_name: str        # Current task name
    attempt_number: int   # Retry attempt (1-indexed)
    raw_context: Any      # Original context for advanced use
```

## File Structure

```
mageflow/
├── adapters/
│   ├── __init__.py
│   ├── protocols.py        # Protocol definitions
│   ├── registry.py         # Adapter registration
│   ├── ARCHITECTURE.md     # This document
│   │
│   ├── hatchet/
│   │   ├── __init__.py
│   │   ├── adapter.py      # HatchetAdapter implementation
│   │   ├── context.py      # HatchetTaskContext
│   │   ├── workflow.py     # HatchetWorkflowAdapter
│   │   ├── framework_tasks.py
│   │   └── invoker.py
│   │
│   └── taskiq/
│       ├── __init__.py
│       ├── adapter.py      # TaskIQAdapter skeleton
│       ├── context.py      # TaskIQTaskContext
│       ├── framework_tasks.py
│       └── workflow_handlers.py
│
├── client.py               # Entry point (type detection HERE ONLY)
├── callbacks.py            # Task wrappers (adapter-agnostic)
├── startup.py              # Initialization (adapter-agnostic)
├── invokers/
│   └── base.py            # BaseInvoker protocol
│
└── ... (rest of package)
```

## How Context Works Differently

### Hatchet
```python
# Hatchet passes context as function parameter
async def task(msg: Message, ctx: Context):
    ctx.log("Hello")
    ctx.additional_metadata  # Access metadata
    ctx.workflow_id          # Get execution ID
```

### TaskIQ
```python
# TaskIQ doesn't have context - metadata is in message
async def task(msg: dict):
    task_data = msg.get("_mageflow_task_data", {})
    # Use standard logging
```

### Mageflow (Unified)
```python
# Mageflow normalizes both to TaskContext
@mage.task(name="my_task")
@mage.with_ctx  # Request context
async def task(msg, task_context: TaskContext):
    task_context.log("Hello")  # Works with any adapter
    task_context.execution_info.workflow_id  # Normalized access
```

## Adding a New Task Manager

To add support for a new task manager (e.g., Celery):

### 1. Create Adapter Directory

```
mageflow/adapters/celery/
├── __init__.py
├── adapter.py
├── context.py
├── workflow.py
└── framework_tasks.py
```

### 2. Implement TaskContext

```python
# adapters/celery/context.py
from mageflow.adapters.protocols import TaskContext, TaskExecutionInfo

class CeleryTaskContext:
    def __init__(self, celery_task, execution_info: TaskExecutionInfo):
        self._task = celery_task
        self._execution_info = execution_info

    @property
    def execution_info(self) -> TaskExecutionInfo:
        return self._execution_info

    def log(self, message: str) -> None:
        # Use Celery's logging
        self._task.update_state(state='PROGRESS', meta={'log': message})

    async def cancel(self) -> None:
        # Revoke the task
        self._task.request.revoke()

    def refresh_timeout(self, duration: timedelta) -> None:
        # Celery soft time limit extension (if supported)
        pass
```

### 3. Implement Adapter

```python
# adapters/celery/adapter.py
from mageflow.adapters.protocols import TaskManagerAdapter, TaskManagerType
from mageflow.adapters.registry import register_adapter

@register_adapter(TaskManagerType.CELERY)  # Add to enum first
class CeleryAdapter(TaskManagerAdapter):
    adapter_type = TaskManagerType.CELERY

    def __init__(self, app=None):
        self._app = app or Celery()

    def task(self, name=None, **options):
        def decorator(func):
            # Wrap with Mageflow callback handler
            # Register with Celery
            return self._app.task(name=name, **options)(wrapped_func)
        return decorator

    # ... implement other methods
```

### 4. Register in Factory

```python
# client.py - Add to Mageflow() function
def Mageflow(
    celery_app: Any = None,  # Add parameter
    ...
):
    if celery_app is not None:
        adapter_type = TaskManagerType.CELERY
        adapter_config["app"] = celery_app
    # ...
```

### 5. Add to TaskManagerType Enum

```python
# adapters/protocols.py
class TaskManagerType(Enum):
    HATCHET = auto()
    TASKIQ = auto()
    CELERY = auto()  # Add new type
```

## Migration Guide

### From Old Code (Hatchet-specific)

```python
# Old
from hatchet_sdk import Hatchet, Context
from mageflow import Mageflow

hatchet = Hatchet()
mage = Mageflow(hatchet)

@mage.task(name="my_task")
async def my_task(msg: Message, ctx: Context):
    ctx.log("Processing...")  # Direct Hatchet ctx usage
```

### To New Code (Adapter-agnostic)

```python
# New
from mageflow import Mageflow
from mageflow.adapters.protocols import TaskContext

# Still works with Hatchet
from hatchet_sdk import Hatchet
mage = Mageflow(hatchet_client=Hatchet())

# Or with TaskIQ
# from taskiq_redis import RedisBroker
# mage = Mageflow(taskiq_broker=RedisBroker(...))

@mage.task(name="my_task")
@mage.with_ctx  # Request normalized context
async def my_task(msg: Message, ctx: TaskContext):
    ctx.log("Processing...")  # Works with any adapter!
```

## Benefits

1. **Single Codebase**: No duplicate logic for different task managers
2. **Easy to Add**: New task managers only need adapter implementation
3. **Testable**: Can mock adapters for testing
4. **Type Safe**: Protocol interfaces provide clear contracts
5. **Maintainable**: Changes to one adapter don't affect others
