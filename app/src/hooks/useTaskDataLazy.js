import { useState, useCallback, useRef } from 'react';

const LOADING_STATES = {
  IDLE: 'idle',
  LOADING: 'loading',
  LOADED: 'loaded',
  ERROR: 'error',
};

const MAX_DEPTH = 10;

export function useTaskDataLazy() {
  const [tasks, setTasks] = useState({});
  const [taskDepths, setTaskDepths] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [loadingStates, setLoadingStates] = useState({});
  const autoLoadingRef = useRef(false);

  const getTaskLoadingState = useCallback((taskId) => {
    return loadingStates[taskId] || { children: LOADING_STATES.IDLE, callbacks: LOADING_STATES.IDLE };
  }, [loadingStates]);

  const updateLoadingState = useCallback((taskId, type, state) => {
    setLoadingStates(prev => ({
      ...prev,
      [taskId]: {
        ...prev[taskId],
        [type]: state,
      },
    }));
  }, []);

  const fetchChildrenInternal = useCallback(async (taskId, page = 0, size = 10) => {
    updateLoadingState(taskId, 'children', LOADING_STATES.LOADING);
    try {
      const response = await fetch(`/api/tasks/${taskId}/children?page=${page}&size=${size}`);
      const data = await response.json();
      if (data.error) throw new Error(data.error);

      const newChildIds = Object.keys(data.children);

      setTasks(prev => {
        const updated = { ...prev };

        Object.entries(data.children).forEach(([childId, childData]) => {
          updated[childId] = childData;
        });

        if (updated[taskId]) {
          const existingTasks = updated[taskId].tasks || [];
          updated[taskId] = {
            ...updated[taskId],
            tasks: [...new Set([...existingTasks, ...newChildIds])],
            childrenLoaded: !data.hasMore,
            childrenPage: page,
            childrenHasMore: data.hasMore,
          };
        }

        return updated;
      });

      setLoadingStates(prev => {
        const updated = { ...prev };
        newChildIds.forEach(childId => {
          if (!updated[childId]) {
            updated[childId] = { children: LOADING_STATES.IDLE, callbacks: LOADING_STATES.IDLE };
          }
        });
        return updated;
      });

      updateLoadingState(taskId, 'children', data.hasMore ? LOADING_STATES.IDLE : LOADING_STATES.LOADED);
      return { ...data, newChildIds };
    } catch (err) {
      updateLoadingState(taskId, 'children', LOADING_STATES.ERROR);
      throw err;
    }
  }, [updateLoadingState]);

  const fetchCallbacksInternal = useCallback(async (taskId) => {
    updateLoadingState(taskId, 'callbacks', LOADING_STATES.LOADING);
    try {
      const response = await fetch(`/api/tasks/${taskId}/callbacks`);
      const data = await response.json();
      if (data.error) throw new Error(data.error);

      const allCallbackIds = [...(data.successCallbacks || []), ...(data.errorCallbacks || [])];

      setTasks(prev => {
        const updated = { ...prev };

        Object.entries(data.callbacks).forEach(([callbackId, callbackData]) => {
          updated[callbackId] = callbackData;
        });

        if (updated[taskId]) {
          updated[taskId] = {
            ...updated[taskId],
            successCallbacks: data.successCallbacks,
            errorCallbacks: data.errorCallbacks,
            callbacksLoaded: true,
            hasCallbacksToLoad: false,
          };
        }

        return updated;
      });

      setLoadingStates(prev => {
        const updated = { ...prev };
        allCallbackIds.forEach(callbackId => {
          if (!updated[callbackId]) {
            updated[callbackId] = { children: LOADING_STATES.IDLE, callbacks: LOADING_STATES.IDLE };
          }
        });
        return updated;
      });

      updateLoadingState(taskId, 'callbacks', LOADING_STATES.LOADED);
      return { ...data, allCallbackIds };
    } catch (err) {
      updateLoadingState(taskId, 'callbacks', LOADING_STATES.ERROR);
      throw err;
    }
  }, [updateLoadingState]);

  const autoLoadToDepth = useCallback(async (taskId, currentDepth, tasksSnapshot) => {
    if (currentDepth >= MAX_DEPTH) return;

    const task = tasksSnapshot[taskId];
    if (!task) return;

    const newDepths = { [taskId]: currentDepth };
    const tasksToProcess = [];

    if (task.totalChildren > 0 && !task.childrenLoaded) {
      try {
        const data = await fetchChildrenInternal(taskId, 0, task.totalChildren);
        for (const childId of data.newChildIds) {
          newDepths[childId] = currentDepth + 1;
          tasksToProcess.push({ id: childId, depth: currentDepth + 1 });
        }
      } catch (err) {
        console.error(`Failed to load children for ${taskId}:`, err);
      }
    }

    if (task.hasCallbacksToLoad) {
      try {
        const data = await fetchCallbacksInternal(taskId);
        for (const callbackId of data.allCallbackIds) {
          newDepths[callbackId] = currentDepth + 1;
          tasksToProcess.push({ id: callbackId, depth: currentDepth + 1 });
        }
      } catch (err) {
        console.error(`Failed to load callbacks for ${taskId}:`, err);
      }
    }

    setTaskDepths(prev => ({ ...prev, ...newDepths }));

    for (const { id, depth } of tasksToProcess) {
      setTasks(currentTasks => {
        autoLoadToDepth(id, depth, currentTasks);
        return currentTasks;
      });
    }
  }, [fetchChildrenInternal, fetchCallbacksInternal]);

  const fetchRootTasks = useCallback(async () => {
    setLoading(true);
    setError(null);
    autoLoadingRef.current = true;
    try {
      const response = await fetch('/api/tasks/roots');
      const data = await response.json();
      if (data.error) throw new Error(data.error);
      setTasks(data.tasks);

      const initialStates = {};
      const initialDepths = {};
      Object.keys(data.tasks).forEach(taskId => {
        initialStates[taskId] = { children: LOADING_STATES.IDLE, callbacks: LOADING_STATES.IDLE };
        initialDepths[taskId] = 0;
      });
      setLoadingStates(initialStates);
      setTaskDepths(initialDepths);

      setLoading(false);

      for (const taskId of Object.keys(data.tasks)) {
        await autoLoadToDepth(taskId, 0, data.tasks);
      }
    } catch (err) {
      setError(err.message);
      setTasks({});
      setLoading(false);
    } finally {
      autoLoadingRef.current = false;
    }
  }, [autoLoadToDepth]);

  const fetchChildren = useCallback(async (taskId, page = 0, size = 10) => {
    const currentDepth = taskDepths[taskId] || 0;
    const data = await fetchChildrenInternal(taskId, page, size);

    const newDepths = {};
    for (const childId of data.newChildIds) {
      newDepths[childId] = currentDepth + 1;
    }
    setTaskDepths(prev => ({ ...prev, ...newDepths }));

    return data;
  }, [fetchChildrenInternal, taskDepths]);

  const fetchCallbacks = useCallback(async (taskId) => {
    const currentDepth = taskDepths[taskId] || 0;
    const data = await fetchCallbacksInternal(taskId);

    const newDepths = {};
    for (const callbackId of data.allCallbackIds) {
      newDepths[callbackId] = currentDepth + 1;
    }
    setTaskDepths(prev => ({ ...prev, ...newDepths }));

    return data;
  }, [fetchCallbacksInternal, taskDepths]);

  const loadMoreChildren = useCallback(async (taskId) => {
    const task = tasks[taskId];
    if (!task) return;

    const currentPage = task.childrenPage ?? -1;
    return fetchChildren(taskId, currentPage + 1);
  }, [tasks, fetchChildren]);

  const loadMore = useCallback(async (taskId) => {
    const task = tasks[taskId];
    if (!task) return;

    const currentDepth = taskDepths[taskId] || 0;

    if (task.totalChildren > 0 && !task.childrenLoaded) {
      const data = await fetchChildrenInternal(taskId, 0, task.totalChildren);
      const newDepths = {};
      for (const childId of data.newChildIds) {
        newDepths[childId] = currentDepth + 1;
      }
      setTaskDepths(prev => ({ ...prev, ...newDepths }));

      for (const childId of data.newChildIds) {
        setTasks(currentTasks => {
          autoLoadToDepth(childId, currentDepth + 1, currentTasks);
          return currentTasks;
        });
      }
    }

    if (task.hasCallbacksToLoad) {
      const data = await fetchCallbacksInternal(taskId);
      const newDepths = {};
      for (const callbackId of data.allCallbackIds) {
        newDepths[callbackId] = currentDepth + 1;
      }
      setTaskDepths(prev => ({ ...prev, ...newDepths }));

      for (const callbackId of data.allCallbackIds) {
        setTasks(currentTasks => {
          autoLoadToDepth(callbackId, currentDepth + 1, currentTasks);
          return currentTasks;
        });
      }
    }
  }, [tasks, taskDepths, fetchChildrenInternal, fetchCallbacksInternal, autoLoadToDepth]);

  return {
    tasks,
    taskDepths,
    loading,
    error,
    loadingStates,
    getTaskLoadingState,
    fetchRootTasks,
    fetchChildren,
    fetchCallbacks,
    loadMoreChildren,
    loadMore,
    refetch: fetchRootTasks,
    maxDepth: MAX_DEPTH,
  };
}

export { LOADING_STATES, MAX_DEPTH };
