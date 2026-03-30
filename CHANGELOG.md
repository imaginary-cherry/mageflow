# Changelog

## [0.3.5]

### 🐛 Fixed

- **Retry Cache Key Collision**: Fixed a bug where `SignatureRetryCache` the same cache object for all instances of the same task, now each task run has different cache instance.

## [0.3.4]

### ✨ Added

- **Testing Client (`mageflow.testing`)**: New pytest plugin providing a `TestClientAdapter` for testing mageflow workflows without a live Hatchet or Redis backend.
  - `mageflow_client` fixture with automatic setup/teardown
  - Typed dispatch records: `TaskDispatchRecord`, `SwarmDispatchRecord`, `ChainDispatchRecord`
  - Assertion API: `assert_task_dispatched`, `assert_swarm_dispatched`, `assert_chain_dispatched` with subset and exact matching
  - Local execution mode for running task handlers in-process
  - `fakeredis` backend support for dual-backend testing (real Redis vs in-memory)
  - Configurable via `pyproject.toml` `[tool.mageflow.testing]` section
- **Integration Tests for Testing Plugin**: User-workflow integration tests covering task, swarm, and chain dispatch scenarios.


### 🐛 Fixed

- **Chain Creation Inside `abounded_field`**: Fixed a bug where creating a chain inside an `abounded_field` context failed due to a nested pipeline conflict. The chain creator now correctly reuses the existing Redis pipeline instead of creating a conflicting one.
- **Fix retry counter**: We now retry total of 4 times for setting retries=3 (like hatchet does by default)
- **Timeout/Cancellation Retry**: We now retry for timeout as well.

### 🔄 Changed

- **`abounded_field` Moved to `thirdmagic`**: `abounded_field` is now exported from `thirdmagic` instead of being an alias in `mageflow`. This makes it available to `thirdmagic`-only consumers without requiring a `mageflow` dependency.

### 🛠️ Technical Improvements

- **`abounded_field` Test Suite**: Added comprehensive tests covering signatures, chains, swarms, and mixed combinations inside `abounded_field`.
- **Retry Integration Tests**: Added `retry_timeout_task` worker and test cases verifying retry behavior for both timeout and error scenarios.


## [0.3.3]

### ✨ Added

- **Signature Retry Cache**: Durable tasks are now idempotent for creating signatures, i.e. they won't create duplicate signatures on retry, they will use the one created in the original run.

## [0.3.2]

### ✨ Added

- **Bulk Task Addition to Swarm**: `aio_run_in_swarm()` now accepts a list of tasks, scheduling multiple tasks in a single call with a shared message.
  - New `aio_run_tasks_in_swarm()` method for adding multiple tasks with individual messages per task.
  - Example: `await swarm.aio_run_in_swarm([t1, t2], msg)`
- **Exposed `abounded_field`**: A new context manager that allows multi-signature updates in a single transaction.
- **Lint CI Job**: Added `ruff` and `black` lint checks to the CI pipeline.
- **CodeRabbit Configuration**: Added `.coderabbit.yaml` for automated code review on PRs.

### 🐛 Fixed

- **Race Condition in Swarm Task Publishing**: Tasks are now saved to the swarm atomically alongside their parameter updates, preventing `fill_running_tasks` from publishing tasks before their kwargs are set.

### 🛠️ Technical Improvements

- **Rapyer version bump**: `thirdmagic` now requires `rapyer>=1.2.5` to support atomic add-task + update-params transactions.
- **Race condition tests**: Added unit tests verifying that tasks are never published before being fully configured.


## [0.3.1]

### ✨ Added

- **Configurable TTL for Signatures**: Added `MageflowConfig` with per-signature-type TTL settings for active and post-completion states.
  - `TTLConfig` controls general active/done TTL defaults
  - `SignatureTTLConfig` allows overriding TTL per signature type (task, chain, swarm)
  - Pass config via `Mageflow(hatchet, redis, config=MageflowConfig(ttl=TTLConfig(...)))`
- **`SignatureConfig` model in `thirdmagic`**: New `SignatureSettings` class variable on `Signature` for configurable `ttl_when_sign_done`.

### 🔄 Changed

- **Signature cleanup TTL**: `Signature.remove_task()` now uses the configurable `SignatureSettings.ttl_when_sign_done` instead of the hardcoded `REMOVED_TASK_TTL` constant.


### 🐛 Fixed
- **Swarm bug**: Fixed a bug that causes swarm concurrency to fill without actually tasks running.


## [0.3.0]

### 🚀 Major Changes
- **Monorepo Split**: Restructured from a single package into a multi-package workspace using `uv` workspaces.
  - `libs/mageflow` — Core task orchestration engine
  - `libs/third-magic` (`thirdmagic`) — Shared models, signatures, and task definitions
  - `libs/mage-voyance` — Visualizer (extracted from `mageflow/visualizer`)
- **Client Adapter Pattern**: We changed the design to be ready for future support of additional task managers (like temporal). We extracted the hatchet unique code to client module, there we handle all the hatchet code 

### ✨ Added
- **`mageflow-mcp` Package**: New MCP (Model Context Protocol) server for workflow observability, enabling AI agents to inspect mageflow workflows.
  - MCP tools: `get_signature`, `list_signatures`, `list_registered_tasks`, `get_container_summary`, `list_sub_tasks`, `get_logs`

### 🔄 Changed
- **BREAKING — Package Imports**: All imports changed due to the split. Core orchestration from `mageflow`, shared models from `thirdmagic`.
- **Swarm Task Calling**: All swarm tasks will be called from `fill_running_tasks` workflow. This is an inner task of mageflow, it is a gateway for publishing new tasks.
- **Task Lock Responsibility**: Lock management moved from `fill_running_tasks` to the task client layer.
- **Hatchet SDK Requirement**: Now requires `hatchet-sdk>=1.22.5`.

### 🐛 Fixed
- **Task Cancellation Handling**: We dont retry task when it is cancelled or when there is a timeout.

### 🛠️ Technical Improvements
- **Per-package CI coverage**: Coverage pipeline reports per-package results with tags.
- **Publish pipeline for thirdmagic**: CI can now publish the `thirdmagic` package independently.


## [0.2.0]

### 🏗️ Design Changes
- **Nested Tasks Redesign**: We change how nested task (like task in a chain) alert the parent task on status change. This will help save a lot of memory in redis and have faster execution. For that we added:
  - **Container sub-task hooks**: `on_sub_task_done()` and `on_sub_task_error()` abstract methods on `ContainerTaskSignature` for handling child task lifecycle events.
  - **BREAKING** - Removed `task_identifiers` from `TaskSignature`: Replaced by `signature_container_id` for parent reference.

### ✨ Added
- **`aio_run_in_swarm()` method**: Add and schedule a task in a running swarm in a single call, replacing the previous `add_task()` + `aio_run_no_wait()` two-step pattern.
- **Chain kwargs forwarding**: Chains now accept `**kwargs` that are forwarded to all sub-tasks during execution.

### 🔄 Changed
- **BREAKING** - Removed `BatchItemTaskSignature`: Swarm tasks are no longer wrapped in batch item signatures. Tasks run directly within the swarm.
- **BREAKING** - Removed `add_task()` from swarm: Use `aio_run_in_swarm()` instead.
- **BREAKING** - Removed `add_callbacks()` from `TaskSignature`: Callbacks are now set at creation time only.
- **All internal tasks are durable**: Chain and swarm infrastructure tasks now use `durable_task` for crash recovery.

### 🛠️ Technical Improvements
- **Task data parameter consolidation**: Only `task_id` is sent as task metadata instead of a full `task_data` dictionary. This will allow users to filter workflow base on task id and will save data that is sent in tasks.

### 🧪 Tests
- **Unit tests for handle decorator**: Added comprehensive tests for `handle_task_callback` decorator.
- **Unit tests for signature creation**: Added tests for `TaskSignatureOptions` and `resolve_signature_key`.


## [0.1.1]

### 🐛 Fixed
- **Native workflow execution**: Fixed some bugs that prevented running tasks natively (no mageflow support)


## [0.1.0]

### ✨ Added
- **Signature TTL**: Time-To-Live set to 1 day for automatic expiration

### 🐛 Fixed
- **Idempotent Swarm Tasks**: Swarm task execution is now idempotent, preventing duplicate execution on retries or crash recovery
  - Tasks track publishing state to avoid re-publishing already-running tasks
  - `fill_running_tasks` workflow handles task distribution atomically
- **Idempotent Chain Workflows**: Chain workflows now support crash recovery with idempotent task transitions


## [0.0.4]
### ✨ Added
- `stagger_execution` decorator for deadlock prevention through random task staggering
- `close_on_max_task` flag in `add_task` method - automatically closes task when maximum number of tasks (from config) is reached (can be disabled by setting flag to False)

### 🐛 Fixed
- Support Hatchet retries with signature
- Error callbacks now wait until all retries are completed or stopped before activation


## [0.0.3]
Fixed a bug for running chain in swarms


## [0.0.2]
Stability - Limit version for rapyer


## [0.0.1]
First release
