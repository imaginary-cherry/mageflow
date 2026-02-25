# Call With Callback

The callback system in MageFlow allows you to create robust, event-driven workflows with automatic success and error handling. This documentation covers the `mageflow.asign()` function, which is the foundation for creating task signatures with callbacks.

## Task Signatures

Task signatures define how a task should be executed, including its configuration, validation, and callback behavior. Think of them as blueprints that specify not just what task to run, but how to handle success and failure scenarios.

### Basic Task Signature

Create a basic task signature using `mageflow.asign()`:

```python
import mageflow

# Create a signature for a registered task
signature = await mageflow.asign("process-data")

# Create a signature from a task function
signature = await mageflow.asign(my_task_function)
```

!!! info "Alternative Client Usage"
    You can also create signatures using the mageflow client instead of the global `mageflow` module:

    ```python
    from mageflow import Mageflow

    hatchet = Mageflow(hatchet, redis)

    signature = await hatchet.asign("process-data")
    signature = await hatchet.asign(my_task_function)
    ```

## Attaching Data with kwargs

Attach additional data to task signatures using keyword arguments. This data becomes available to the task when it executes.

### Basic kwargs Usage

```python
task_signature = await mageflow.asign(
    "send-notification",
    template="welcome_email",
    priority="high",
    retry_count=3
)
```

### Dynamic Data Attachment

Update kwargs after creating the signature:

```python
user_task = await mageflow.asign("process-user-data")

await user_task.kwargs.aupdate(
    user_id="12345",
    preferences={"theme": "dark", "notifications": True},
    processing_mode="batch"
)
```


## Success and Error Callbacks

The power of task signatures lies in their ability to automatically trigger callbacks based on task outcomes.

### Setting Success Callbacks

Success callbacks are executed when a task completes successfully:

```python
success_callback = await mageflow.asign("send-success-email")
audit_callback = await mageflow.asign("log-completion")

main_task = await mageflow.asign(
    "process-order",
    success_callbacks=[success_callback, audit_callback]
)
```

When a success callback is called, the return value of the function is injected into the parameter marked with `ReturnValue`.

```python
from pydantic import BaseModel
from thirdmagic.message import ReturnValue


class SuccessMessage(BaseModel):
    task_result: ReturnValue[Any]
    field_int: int
    ...


@hatchet.task(input_validator=SuccessMessage)
async def success_callback(msg: SuccessMessage):
    result = msg.task_result
```

!!! info "ReturnValue Annotation"
    ReturnValue tells mageflow that the return value of the function should be injected into the marked parameter.
    ```python
    from pydantic import BaseModel
    from thirdmagic.message import ReturnValue

    class SuccessMessage(BaseModel):
        task_result: ReturnValue[Any]
        field_int: int
    ```

    When no field is marked with ReturnValue, the return value is sent to the field named `mageflow_results`.
    ```python
    class SuccessMessage(BaseModel):
        mageflow_results: str
        field_int: int
    ```


### Setting Error Callbacks

Error callbacks are triggered when a task fails:

```python
error_logger = await mageflow.asign("log-error")
notify_admin = await mageflow.asign("alert-administrator")
retry_handler = await mageflow.asign("schedule-retry")

risky_task = await mageflow.asign(
    "external-api-call",
    error_callbacks=[error_logger, notify_admin, retry_handler]
)
```

For error callbacks, the message will be the same message that was sent to the task itself. You can create a new model with more parameters and bind them to the error callback:

```python
from pydantic import BaseModel


class ErrorMessage(OriginalMessage):
    additional_field1: int
    additional_field2: str
    ...


@hatchet.task(input_validator=ErrorMessage)
async def error_callback(msg: ErrorMessage):
    result = msg.task_result


error_logger = await mageflow.asign(error_callback, additional_field1=12345, additional_field2="test")
signature = await mageflow.asign("task", error_callbacks=[error_logger])
```

## Advanced Signature Configuration

### Model Validation

Specify input validation for your task signatures:

```python
validated_task = await mageflow.asign(
    "validate-data",
    model_validators=ContextMessage
)
```

Usually you don't have to do this, as this is done automatically. But you can override the default model_validator with your own.
