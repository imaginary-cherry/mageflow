# Changelog

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
