from mageflow.invokers.base import TaskClientAdapter


def init_mageflow_internal_tasks(adapter: TaskClientAdapter) -> list:
    """
    Register and return internal mageflow infrastructure tasks
    using the provided client adapter.

    This delegates to the adapter's init_internal_tasks() method,
    which knows how to register chain/swarm tasks with its specific client.
    """
    return adapter.init_internal_tasks()


# Backward-compatible alias
def init_mageflow_hatchet_tasks(hatchet_or_adapter) -> list:
    """
    Backward-compatible wrapper.

    Accepts either a Hatchet client (legacy) or a TaskClientAdapter.
    """
    if isinstance(hatchet_or_adapter, TaskClientAdapter):
        return init_mageflow_internal_tasks(hatchet_or_adapter)

    # Legacy path: wrap Hatchet client in adapter
    from mageflow.invokers.hatchet import HatchetClientAdapter

    adapter = HatchetClientAdapter(hatchet_or_adapter)
    return adapter.init_internal_tasks()
