"""
Hatchet task manager adapter.

This module provides the complete Hatchet implementation of the TaskManagerAdapter.
All Hatchet-specific code is contained here, making it the single point of change
when Hatchet's API changes.
"""
from datetime import timedelta
from typing import Any, Callable

from hatchet_sdk import Hatchet, Worker, Context
from hatchet_sdk import NonRetryableException
from hatchet_sdk.labels import DesiredWorkerLabel
from hatchet_sdk.rate_limit import RateLimit
from hatchet_sdk.runnables.types import (
    StickyStrategy,
    ConcurrencyExpression,
    ConcurrencyLimitStrategy,
    DefaultFilter,
    EmptyModel,
)
from hatchet_sdk.runnables.workflow import BaseWorkflow
from hatchet_sdk.worker.worker import LifespanFn
from pydantic import BaseModel

from mageflow.adapters.protocols import (
    TaskManagerAdapter,
    TaskManagerType,
    TaskExecutionInfo,
    TaskContext,
    WorkflowAdapter,
    WorkerAdapter,
    TaskFunc,
)
from mageflow.adapters.registry import register_adapter
from mageflow.adapters.hatchet.context import (
    HatchetTaskContext,
    extract_hatchet_execution_info,
    create_hatchet_task_context,
)
from mageflow.adapters.hatchet.workflow import HatchetWorkflowAdapter


@register_adapter(TaskManagerType.HATCHET)
class HatchetAdapter(TaskManagerAdapter):
    """
    Hatchet implementation of TaskManagerAdapter.

    This adapter wraps the Hatchet SDK and provides the normalized interface
    that Mageflow uses internally.
    """

    adapter_type = TaskManagerType.HATCHET

    def __init__(
        self,
        client: Hatchet | None = None,
        debug: bool = False,
    ):
        """
        Initialize the Hatchet adapter.

        Args:
            client: Existing Hatchet client (creates new one if None)
            debug: Enable debug mode
        """
        if client is None:
            client = Hatchet(debug=debug)
        self._client = client

        # Create a separate client with empty namespace for workflow creation
        # This is a Hatchet-specific pattern
        config = client._client.config.model_copy(deep=True)
        config.namespace = ""
        self._workflow_client = Hatchet(config=config, debug=debug)

    @property
    def native_client(self) -> Hatchet:
        """Get the native Hatchet client."""
        return self._client

    @property
    def workflow_client(self) -> Hatchet:
        """Get the Hatchet client used for workflow creation."""
        return self._workflow_client

    def task(
        self,
        name: str | None = None,
        **options: Any,
    ) -> Callable[[TaskFunc], TaskFunc]:
        """Create a Hatchet task decorator."""
        # Convert generic options to Hatchet-specific options
        hatchet_options = self._convert_task_options(options)
        return self._client.task(name=name, **hatchet_options)

    def durable_task(
        self,
        name: str | None = None,
        **options: Any,
    ) -> Callable[[TaskFunc], TaskFunc]:
        """Create a Hatchet durable task decorator."""
        hatchet_options = self._convert_task_options(options)
        return self._client.durable_task(name=name, **hatchet_options)

    def _convert_task_options(self, options: dict) -> dict:
        """
        Convert generic TaskOptions to Hatchet-specific options.

        This handles the translation from normalized options to Hatchet's
        specific option names and types.
        """
        hatchet_options = {}

        # Direct mappings
        direct_mappings = [
            "description",
            "input_validator",
            "retries",
            "execution_timeout",
            "schedule_timeout",
            "on_events",
            "on_crons",
            "default_priority",
            "backoff_factor",
            "backoff_max_seconds",
            "version",
        ]
        for key in direct_mappings:
            if key in options:
                hatchet_options[key] = options[key]

        # Handle concurrency (convert from generic to Hatchet's ConcurrencyExpression)
        if "concurrency_key" in options or "concurrency_limit" in options:
            concurrency_key = options.get("concurrency_key")
            concurrency_limit = options.get("concurrency_limit", 1)
            if concurrency_key:
                hatchet_options["concurrency"] = ConcurrencyExpression(
                    expression=concurrency_key,
                    max_runs=concurrency_limit,
                    limit_strategy=ConcurrencyLimitStrategy.CANCEL_NEWEST,
                )

        # Pass through Hatchet-specific options
        hatchet_specific = [
            "sticky",
            "rate_limits",
            "desired_worker_labels",
            "default_filters",
            "concurrency",  # Allow direct ConcurrencyExpression pass-through
        ]
        for key in hatchet_specific:
            if key in options:
                hatchet_options[key] = options[key]

        return hatchet_options

    def worker(
        self,
        name: str,
        workflows: list[Any] | None = None,
        lifespan: Callable | None = None,
        **options: Any,
    ) -> WorkerAdapter:
        """Create a Hatchet worker."""
        worker_options = self._convert_worker_options(options)

        return HatchetWorkerAdapter(
            self._client.worker(
                name,
                workflows=workflows or [],
                lifespan=lifespan,
                **worker_options,
            )
        )

    def _convert_worker_options(self, options: dict) -> dict:
        """Convert generic WorkerOptions to Hatchet-specific options."""
        hatchet_options = {}

        direct_mappings = ["slots", "durable_slots", "labels"]
        for key in direct_mappings:
            if key in options:
                hatchet_options[key] = options[key]

        return hatchet_options

    def workflow(
        self,
        name: str,
        input_validator: type[BaseModel] | None = None,
        task_ctx: dict | None = None,
        workflow_params: dict | None = None,
        return_value_field: str | None = None,
    ) -> WorkflowAdapter:
        """Create a Hatchet workflow adapter."""
        native_workflow = self._workflow_client.workflow(
            name=name,
            input_validator=input_validator,
        )
        return HatchetWorkflowAdapter(
            workflow=native_workflow,
            task_ctx=task_ctx or {},
            workflow_params=workflow_params or {},
            return_value_field=return_value_field,
        )

    def extract_execution_info(self, raw_context: Any, message: Any) -> TaskExecutionInfo:
        """Extract TaskExecutionInfo from Hatchet Context."""
        if not isinstance(raw_context, Context):
            raise TypeError(
                f"Expected Hatchet Context, got {type(raw_context).__name__}"
            )
        return extract_hatchet_execution_info(raw_context, message)

    def create_task_context(self, raw_context: Any, message: Any) -> TaskContext:
        """Create a TaskContext wrapper for Hatchet Context."""
        if not isinstance(raw_context, Context):
            raise TypeError(
                f"Expected Hatchet Context, got {type(raw_context).__name__}"
            )
        return create_hatchet_task_context(raw_context, message)

    def create_framework_tasks(self) -> list[Any]:
        """Create internal framework tasks for chain/swarm."""
        from mageflow.adapters.hatchet.framework_tasks import (
            create_hatchet_framework_tasks,
        )

        return create_hatchet_framework_tasks(self._client)

    def should_retry(
        self, execution_info: TaskExecutionInfo, exception: Exception
    ) -> bool:
        """Check if task should retry (Hatchet-specific logic)."""
        # Hatchet's NonRetryableException prevents retries
        if isinstance(exception, NonRetryableException):
            return False
        return True

    def get_non_retryable_exception(self) -> type[Exception]:
        """Get the Hatchet NonRetryableException class."""
        return NonRetryableException


class HatchetWorkerAdapter:
    """WorkerAdapter implementation for Hatchet Worker."""

    def __init__(self, worker: Worker):
        self._worker = worker

    @property
    def native_worker(self) -> Worker:
        """Get the native Hatchet Worker."""
        return self._worker

    async def async_start(self) -> None:
        """Start the worker asynchronously."""
        await self._worker.async_start()

    def start(self) -> None:
        """Start the worker synchronously."""
        self._worker.start()
