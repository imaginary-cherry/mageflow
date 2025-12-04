# Chain API Reference

This page provides detailed API documentation for chain functionality in the Task Orchestrator.

## orchestrator.chain()

Create a new task chain for sequential execution.

```python
async def chain(
    tasks: List[TaskSignatureConvertible],
    name: Optional[str] = None,
    error: Optional[TaskInputType] = None,
    success: Optional[TaskInputType] = None,
) -> ChainTaskSignature
```

**Parameters:**
- `tasks`: List of tasks to execute sequentially (minimum 2 tasks required)
- `name`: Optional name for the chain (defaults to first task's name)
- `error`: Task to execute when any task in the chain fails
- `success`: Task to execute when all tasks complete successfully

**Returns:** `ChainTaskSignature` - The chain task signature

**Raises:**
- `ValueError`: If fewer than 2 tasks are provided

## ChainTaskSignature

The main chain class that manages sequential task execution.

### Properties

- `tasks`: List of task IDs in the chain sequence
- `task_name`: Name of the chain (derived from first task if not specified)
- `success_callbacks`: Tasks executed when chain completes successfully
- `error_callbacks`: Tasks executed when any task fails

### Methods

#### workflow()

Get the workflow representation starting from the first task.

```python
async def workflow(**task_additional_params) -> BaseWorkflow
```

**Parameters:**
- `**task_additional_params`: Additional parameters for workflow creation

**Returns:** Workflow object for the first task in the chain

**Raises:**
- `MissingSignatureError`: If the first task in the chain is not found

#### delete_chain_tasks()

Remove all tasks in the chain.

```python
async def delete_chain_tasks(with_errors: bool = True, with_success: bool = True)
```

**Parameters:**
- `with_errors`: Whether to delete error callback tasks
- `with_success`: Whether to delete success callback tasks

#### change_status()

Change the status of the entire chain and all its tasks.

```python
async def change_status(status: SignatureStatus)
```

**Parameters:**
- `status`: New status to apply to the chain and all tasks

#### suspend()

Suspend the entire chain and all its tasks.

```python
async def suspend()
```

Suspends all tasks in the chain and sets the chain status to `SUSPENDED`.

#### resume()

Resume the chain and all its tasks.

```python
async def resume()
```

Resumes all tasks in the chain and restores the previous status.

#### interrupt()

Interrupt the chain and all its tasks.

```python
async def interrupt()
```

Interrupts all tasks in the chain and sets the status to `INTERRUPTED`.

## Chain Workflow Structure

When a chain is created, the orchestrator automatically:

1. **Links Tasks Sequentially**: Each task's success callback points to the next task
2. **Creates Error Handlers**: Each task gets an error callback that stops the chain
3. **Manages Data Flow**: Output from each task becomes input to the next task
4. **Handles Completion**: The final task triggers the chain's success callback

### Internal Chain Management

Chains use internal workflow tasks for lifecycle management:

- `ON_CHAIN_END`: Triggered when the chain completes successfully
- `ON_CHAIN_ERROR`: Triggered when any task in the chain fails

These internal tasks handle:
- Executing user-defined success/error callbacks
- Cleaning up chain resources
- Managing chain state transitions

## Error Classes

### MissingSignatureError

Raised when a task in the chain cannot be found during execution.

### ValueError

Raised when attempting to create a chain with fewer than 2 tasks.

## Usage Patterns

### Basic Chain Creation

```python
chain_sig = await orchestrator.chain(
    tasks=[task1, task2, task3],
    name="my-processing-chain"
)
```

### Chain with Callbacks

```python
success_task = await orchestrator.sign("chain-completed")
error_task = await orchestrator.sign("chain-failed")

chain_sig = await orchestrator.chain(
    tasks=[extract, transform, load],
    name="etl-pipeline",
    success=success_task,
    error=error_task
)
```

### Chain Execution

```python
# Start the chain
await chain_sig.aio_run_no_wait(initial_message)

# The chain will:
# 1. Start the first task with initial_message
# 2. Pass first task's output to second task
# 3. Pass second task's output to third task
# 4. Trigger success callback with final output
# 5. Or trigger error callback if any task fails
```

### Chain Management

```python
# Suspend the entire chain
await chain_sig.suspend()

# Resume the chain
await chain_sig.resume()

# Interrupt the chain
await chain_sig.interrupt()

# Check chain status
status = chain_sig.task_status
```

## Data Flow

In a chain, data flows sequentially through tasks:

```python
@hatchet.task()
async def task1(msg: InputMessage) -> OutputMessage1:
    return OutputMessage1(data="processed")

@hatchet.task()  
async def task2(msg: OutputMessage1) -> OutputMessage2:
    # Receives OutputMessage1 from task1
    return OutputMessage2(result=msg.data + "_transformed")

@hatchet.task()
async def task3(msg: OutputMessage2) -> FinalOutput:
    # Receives OutputMessage2 from task2
    return FinalOutput(final=msg.result + "_complete")

# Chain automatically handles the data flow
chain_sig = await orchestrator.chain([task1, task2, task3])
```

## Lifecycle Management

Chains provide comprehensive lifecycle management:

- **Creation**: Links tasks and creates internal handlers
- **Execution**: Manages sequential task execution
- **Error Handling**: Stops execution on first failure
- **Completion**: Triggers callbacks and cleanup
- **Status Management**: Synchronizes status across all tasks
- **Resource Cleanup**: Removes tasks and callbacks when done