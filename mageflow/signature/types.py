from typing import Callable, Any

TaskIdentifierType = str
# Generic task type - can be a workflow object from any client or a plain callable
TaskType = Any | Callable
# Backward-compatible alias
HatchetTaskType = TaskType
