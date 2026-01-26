"""MCP resources for MageFlow workflow documentation."""

WORKFLOW_GUIDE = """
# MageFlow Workflow Guide

MageFlow is a unified task orchestration framework for distributed systems. This guide explains
how to interpret task data, understand task lifecycles, and analyze task graphs.

## Task Types

MageFlow has three main task types:

### 1. TaskSignature (Base Task)
The fundamental building block - a serializable task definition stored in Redis.

**Key Properties:**
- `task_name`: The task identifier/function name
- `kwargs`: Task parameters/inputs
- `task_status`: Current execution status
- `success_callbacks`: List of task IDs to run on success
- `error_callbacks`: List of task IDs to run on failure
- `task_identifiers`: Custom metadata for context-aware callbacks
- `creation_time`: When the task was created

### 2. ChainTaskSignature (Sequential Execution)
Chains multiple tasks sequentially where output of task N becomes input for task N+1.

**Key Properties:**
- `tasks`: Ordered list of task IDs in the chain

**Behavior:**
- Starts with the first task in the list
- On success: executes next task with previous task's output
- On failure: stops immediately, triggers error callbacks
- When complete: triggers success callbacks with final result

### 3. SwarmTaskSignature (Parallel Execution)
Manages parallel execution of multiple tasks with concurrency control.

**Key Properties:**
- `tasks`: All batch item task IDs in the swarm
- `tasks_left_to_run`: Queue of pending tasks waiting for concurrency slot
- `finished_tasks`: Completed task IDs
- `failed_tasks`: Failed task IDs
- `tasks_results`: Collected results from completed tasks
- `current_running_tasks`: Number of currently executing tasks
- `is_swarm_closed`: Whether new tasks can be added
- `config`: SwarmConfig with concurrency settings

**SwarmConfig:**
- `max_concurrency`: Maximum parallel tasks (default: 30)
- `stop_after_n_failures`: Fail-fast threshold (optional)
- `max_task_allowed`: Total task limit (optional)

### 4. BatchItemTaskSignature (Swarm Item Wrapper)
Internal wrapper for each task added to a swarm.

**Key Properties:**
- `swarm_id`: Parent swarm task ID
- `original_task_id`: The actual task being wrapped

## Task Statuses

### SignatureStatus Enum

| Status | Meaning |
|--------|---------|
| `pending` | Task created, waiting to be executed |
| `active` | Task is currently running |
| `suspended` | Task paused gracefully (soft pause) |
| `interrupted` | Task paused aggressively (not fully implemented) |
| `canceled` | Task was canceled and will be deleted |

### Status Transitions

```
             create
                |
                v
           +--------+
           | PENDING|<--------+
           +--------+         |
                |             | resume
                | run         |
                v             |
           +--------+    +-----------+
           | ACTIVE |----| SUSPENDED |
           +--------+    +-----------+
                |
        success | error
                |
                v
        [callbacks triggered]
                |
                v
           [deleted]
```

### How to Interpret Status

1. **pending**: Task is queued. Check `tasks_left_to_run` in swarms to see queue position.

2. **active**: Task is executing. The `worker_task_id` field contains the Hatchet workflow ID.

3. **suspended**: Task was paused before completion. The `kwargs` field contains the saved state.
   Resume will restore the task to its `last_status`.

4. **canceled**: Task was canceled. It will be deleted along with its callbacks.

## Task Graph Structure

### Basic Task Graph
```
TaskA
  |---> success_callbacks: [TaskB, TaskC]
  |---> error_callbacks: [ErrorHandler]
```

### Chain Graph Structure
```
ChainTask (parent)
  |
  +---> tasks: [TaskA, TaskB, TaskC]
  |
  +---> Internal structure:
        TaskA.success_callbacks = [TaskB]
        TaskB.success_callbacks = [TaskC]
        TaskC.success_callbacks = [OnChainEnd]
        All tasks have error_callbacks pointing to OnChainError
```

### Swarm Graph Structure
```
SwarmTask (parent)
  |
  +---> tasks: [BatchItem1, BatchItem2, BatchItem3]
  |
  +---> Each BatchItem:
        - swarm_id: SwarmTask
        - original_task_id: ActualTask
        - success_callbacks: [ON_SWARM_END]
        - error_callbacks: [ON_SWARM_ERROR]
```

## Analyzing Task State

### For a Basic Task
1. Check `status` - is it pending, active, suspended, or canceled?
2. Check `kwargs` - what parameters does it have?
3. Check callback counts - does it have success/error handlers?
4. If suspended, check `last_status` to see what it was doing when paused

### For a Chain
1. Use `get_chain_status` to see overall progress
2. `current_task_index` tells you which task is running (0-indexed)
3. Compare completed vs total to track progress
4. If a task is suspended/failed, the chain stops at that point

### For a Swarm
1. Use `get_swarm_status` for overview:
   - `running_tasks` vs `max_concurrency` shows utilization
   - `tasks_left_to_run` shows queue depth
   - `completed_tasks` + `failed_tasks` = progress
2. Check `is_closed` - if false, more tasks may be added
3. `failed_tasks` count indicates issues
4. `results_count` shows how many results are collected

## Common Analysis Patterns

### Find Stuck Tasks
Look for tasks where:
- Status is `active` but `worker_task_id` is empty (task never started)
- Status is `pending` for a long time
- Chain's `current_task_status` is not progressing

### Understand Failures
1. Get the task with `get_task`
2. Check `error_callbacks` with `get_task_callbacks`
3. For swarms, compare `failed_tasks` count vs total
4. Look at the `kwargs` of failed tasks for context

### Track Progress
- **Chain**: `completed_tasks / total_tasks`
- **Swarm**: `(completed_tasks + failed_tasks) / total_tasks`

### Investigate Dependencies
Use `get_task_graph` to see the full callback chain:
- `children` shows subtasks (for chains/swarms)
- `success_callbacks` shows what runs on success
- `error_callbacks` shows error handlers

## Task ID Format

Task IDs follow this pattern:
```
{TaskType}:{base64_encoded_uuid}
```

Examples:
- `TaskSignature:YWJjZGVm...`
- `ChainTaskSignature:Z2hpamts...`
- `SwarmTaskSignature:bW5vcHFy...`
- `BatchItemTaskSignature:c3R1dnd4...`

The prefix tells you the task type, which determines available properties.

## Callback System

### Success Callbacks
Triggered when a task completes successfully. Receives the task's return value.

### Error Callbacks
Triggered when a task fails. Receives error information.

### Special Callbacks (Internal)
- `ON_CHAIN_END`: Chain completion handler
- `ON_CHAIN_ERROR`: Chain error handler
- `ON_SWARM_START`: Swarm initialization
- `ON_SWARM_END`: Per-item completion in swarm
- `ON_SWARM_ERROR`: Per-item error in swarm

These internal callbacks manage the orchestration logic and should not be manually modified.

## Best Practices for Investigation

1. **Start with `get_task`** to get basic info
2. **Check the type** - behavior varies by task type
3. **For composites**, use specialized tools (`get_chain_status`, `get_swarm_status`)
4. **Use pagination** when there are many subtasks
5. **Follow the graph** with `get_task_graph` to understand full flow
6. **Check callbacks** to understand what happens on success/failure
"""


def get_workflow_guide() -> str:
    """Get the workflow guide resource content."""
    return WORKFLOW_GUIDE
