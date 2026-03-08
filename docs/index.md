<div align="center">
  <img src="logo.png" alt="MageFlow Logo" width="200"/>
  <p>
    <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10+-blue.svg&#63;style=for-the-badge" alt="Python 3.10+" height="28"/></a>
    <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg&#63;style=for-the-badge" alt="License: MIT" height="28"/></a>
    <a href="https://codecov.io/gh/imaginary-cherry/mageflow&#63;flags&#91;0&#93;=mageflow-unit"><img src="https://img.shields.io/codecov/c/gh/imaginary-cherry/mageflow&#63;style=for-the-badge&#38;flag=mageflow-unit" alt="mageflow unit coverage" height="28"/></a>
    <a href="https://codecov.io/gh/imaginary-cherry/mageflow&#63;flags&#91;0&#93;=mageflow-integration"><img src="https://img.shields.io/codecov/c/gh/imaginary-cherry/mageflow&#63;style=for-the-badge&#38;flag=mageflow-integration" alt="mageflow integration coverage" height="28"/></a>
    <a href="https://codecov.io/gh/imaginary-cherry/mageflow&#63;flags&#91;0&#93;=thirdmagic"><img src="https://img.shields.io/codecov/c/gh/imaginary-cherry/mageflow&#63;style=for-the-badge&#38;flag=thirdmagic" alt="thirdmagic coverage" height="28"/></a>
    <a href="https://badge.fury.io/py/mageflow"><img src="https://img.shields.io/pypi/v/mageflow&#63;style=for-the-badge" alt="PyPI version" height="28"/></a>
    <a href="https://pepy.tech/project/mageflow"><img src="https://img.shields.io/pepy/dt/mageflow&#63;style=for-the-badge" alt="Downloads" height="28"/></a>
    <a href="https://imaginary-cherry.github.io/mageflow/"><img src="https://img.shields.io/badge/docs-github.io-blue&#63;style=for-the-badge" alt="Documentation" height="28"/></a>
  </p>
</div>

# MageFlow

<strong>Ma</strong>nage <strong>G</strong>raph <strong>E</strong>xecution <strong>Flow</strong> - This package's purpose is to help users of task managers (like hatchet/taskiq etc) to orchestrate their tasks in an easy way from a single point. This way, it is much easier to flow and change, rather than spreading the flow logic all over your projects.
MageFlow provides a unify interface across different task managers that is fully compatible with the task manager api to execute tasks in chain/parallel/conditional tasks that can be calculated in runtime.

## What is Mageflow?

Mageflow abstracts away the complexity of task management systems, providing a unified interface to:

- **Execute tasks with callbacks**: Run tasks with success and error callbacks for robust error handling
- **Chain tasks together**: Create sequential workflows where tasks depend on the completion of previous tasks
- **Manage task swarms**: Run multiple tasks in parallel with sophisticated coordination and monitoring
- **Handle task lifecycle**: Pause, resume, and monitor task execution with built-in state management

## Key Features

### Task Chaining
Create sequential workflows where each task depends on the previous one's completion. Perfect for multi-step processes where order matters.

```python
import mageflow

# Create a chain of tasks that run sequentially
task_order = [
    preprocess_data_task,
    analyze_data_task,
    generate_report_task
]
workflow = await mageflow.achain(task_order, name="data-pipeline")
```

### Task Swarms
Execute multiple tasks in parallel with intelligent coordination. Ideal for processing large datasets or performing independent operations simultaneously.

```python
import mageflow

# Run multiple tasks in parallel
swarm_tasks = [
    process_user_data_task,
    send_notifications_task,
    update_cache_task
]
parallel_workflow = await mageflow.aswarm(swarm_tasks, task_name="user-processing")
```

### 📞 Callback System
Robust error handling and success callbacks ensure your workflows are resilient and responsive.

```python
from mageflow import handle_task_callback

@hatchet.task(name="my-task")
@handle_task_callback()
async def my_task(message):
    return {"status": "completed"}
```

### Task Signatures
Flexible task definition system with validation, state management, and lifecycle control.

```python
import mageflow

# Create a task signature with callbacks
task_signature = await mageflow.asign(
    "process-order",
    success_callbacks=[send_confirmation_task],
    error_callbacks=[handle_error_task]
)
```

## Core Components

### Task Management
- **Task Registration**: Register tasks with mageflow for centralized management
- **Task Lifecycle**: Control task execution with pause, resume, and cancellation capabilities
- **Task Validation**: Built-in validation for task inputs and outputs using Pydantic models

### Workflow Orchestration
- **Sequential Execution**: Chain tasks together for step-by-step processing
- **Parallel Execution**: Run tasks simultaneously with swarm coordination
- **Conditional Logic**: Execute tasks based on the results of previous tasks

### State Management
- **Persistent State**: Tasks maintain state across executions using Redis backend
- **Status Tracking**: Monitor task progress with detailed status information
- **Recovery**: Resume interrupted workflows from their last known state

### Error Handling
- **Callback-based**: Define custom error handling logic for each task
- **Retry Logic**: Automatic retry mechanisms for failed tasks
- **Graceful Degradation**: Continue workflow execution even when individual tasks fail

## Architecture

The package is built on top of proven task management systems and provides:

- **Backend Agnostic**: Currently supports Hatchet with plans for other backends
- **Redis Storage**: Persistent state management using Redis
- **Async-First**: Built for modern async Python applications
- **Type Safe**: Full type hints and Pydantic model validation
- **Production Ready**: Designed for high-throughput, reliable production use

## Getting Started

To start using MageFlow, you'll need to:

1. **Install** the package and its dependencies
2. **Set up** your task manager backend (e.g., Hatchet)
3. **Configure** Redis for state storage
4. **Define** your tasks and workflows
5. **Run** your tasks

Ready to get started? Check out the [Setup Documentation](setup.md).
