from typing import cast
from unittest.mock import Mock, call

from thirdmagic.task import TaskSignature


def assert_resume_signature(signature: TaskSignature, mock_adapter: Mock):
    tasks_called = [a[0][0] for a in mock_adapter.acall_signature.call_args_list]
    tasks_called = cast(list[TaskSignature], tasks_called)
    task_called_with_id = [task for task in tasks_called if task.key == signature.key]
    assert len(task_called_with_id) == 1, f"Task was resumed more than once"
    mock_adapter.acall_signature.assert_has_awaits(
        [call(task_called_with_id[0], None, set_return_field=False)]
    )
