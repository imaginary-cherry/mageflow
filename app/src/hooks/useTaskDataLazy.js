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
  const pendingUpdatesRef = useRef({ tasks: {}, depths: {}, loadingStates: {} });
  const flushTimeoutRef = useRef(null);

  const flushPendingUpdates = useCallback(() => {
    const pending = pendingUpdatesRef.current;
    if (Object.keys(pending.tasks).length > 0) {
      setTasks(prev => ({ ...prev, ...pending.tasks }));
    }
    if (Object.keys(pending.depths).length > 0) {
      setTaskDepths(prev => ({ ...prev, ...pending.depths }));
    }
    if (Object.keys(pending.loadingStates).length > 0) {
      setLoadingStates(prev => ({ ...prev, ...pending.loadingStates }));
    }
    pendingUpdatesRef.current = { tasks: {}, depths: {}, loadingStates: {} };
  }, []);

  const scheduleFlush = useCallback(() => {
    if (flushTimeoutRef.current) return;
    flushTimeoutRef.current = setTimeout(() => {
      flushTimeoutRef.current = null;
      flushPendingUpdates();
    }, 50);
  }, [flushPendingUpdates]);

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

  const fetchChildrenInternal = useCallback(async (taskId, page = 0, size = 10, batch = false) => {
    if (!batch) {
      updateLoadingState(taskId, 'children', LOADING_STATES.LOADING);
    }
    try {
      const response = await fetch(`/api/tasks/${taskId}/children?page=${page}&size=${size}`);
      const data = await response.json();
      if (data.error) throw new Error(data.error);

      const newChildIds = Object.keys(data.children);

      if (batch) {
        Object.entries(data.children).forEach(([childId, childData]) => {
          pendingUpdatesRef.current.tasks[childId] = childData;
          if (!pendingUpdatesRef.current.loadingStates[childId]) {
            pendingUpdatesRef.current.loadingStates[childId] = { children: LOADING_STATES.IDLE, callbacks: LOADING_STATES.IDLE };
          }
        });

        const existingTasks = pendingUpdatesRef.current.tasks[taskId]?.tasks || tasks[taskId]?.tasks || [];
        pendingUpdatesRef.current.tasks[taskId] = {
          ...(tasks[taskId] || {}),
          ...(pendingUpdatesRef.current.tasks[taskId] || {}),
          tasks: [...new Set([...existingTasks, ...newChildIds])],
          childrenLoaded: !data.hasMore,
          childrenPage: page,
          childrenHasMore: data.hasMore,
        };
        pendingUpdatesRef.current.loadingStates[taskId] = {
          ...(pendingUpdatesRef.current.loadingStates[taskId] || loadingStates[taskId] || {}),
          children: data.hasMore ? LOADING_STATES.IDLE : LOADING_STATES.LOADED,
        };
        scheduleFlush();
      } else {
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
      }

      return { ...data, newChildIds };
    } catch (err) {
      if (!batch) {
        updateLoadingState(taskId, 'children', LOADING_STATES.ERROR);
      }
      throw err;
    }
  }, [updateLoadingState, scheduleFlush, tasks, loadingStates]);

  const fetchCallbacksInternal = useCallback(async (taskId, batch = false) => {
    if (!batch) {
      updateLoadingState(taskId, 'callbacks', LOADING_STATES.LOADING);
    }
    try {
      const response = await fetch(`/api/tasks/${taskId}/callbacks`);
      const data = await response.json();
      if (data.error) throw new Error(data.error);

      const allCallbackIds = [...(data.successCallbacks || []), ...(data.errorCallbacks || [])];

      if (batch) {
        Object.entries(data.callbacks).forEach(([callbackId, callbackData]) => {
          pendingUpdatesRef.current.tasks[callbackId] = callbackData;
          if (!pendingUpdatesRef.current.loadingStates[callbackId]) {
            pendingUpdatesRef.current.loadingStates[callbackId] = { children: LOADING_STATES.IDLE, callbacks: LOADING_STATES.IDLE };
          }
        });

        pendingUpdatesRef.current.tasks[taskId] = {
          ...(tasks[taskId] || {}),
          ...(pendingUpdatesRef.current.tasks[taskId] || {}),
          successCallbacks: data.successCallbacks,
          errorCallbacks: data.errorCallbacks,
          callbacksLoaded: true,
          hasCallbacksToLoad: false,
        };
        pendingUpdatesRef.current.loadingStates[taskId] = {
          ...(pendingUpdatesRef.current.loadingStates[taskId] || loadingStates[taskId] || {}),
          callbacks: LOADING_STATES.LOADED,
        };
        scheduleFlush();
      } else {
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
      }

      return { ...data, allCallbackIds };
    } catch (err) {
      if (!batch) {
        updateLoadingState(taskId, 'callbacks', LOADING_STATES.ERROR);
      }
      throw err;
    }
  }, [updateLoadingState, scheduleFlush, tasks, loadingStates]);

  const autoLoadToDepth = useCallback(async (taskId, currentDepth, tasksSnapshot) => {
    if (currentDepth >= MAX_DEPTH) return;

    const task = pendingUpdatesRef.current.tasks[taskId] || tasksSnapshot[taskId];
    if (!task) return;

    const tasksToProcess = [];
    pendingUpdatesRef.current.depths[taskId] = currentDepth;

    if (task.totalChildren > 0 && !task.childrenLoaded) {
      try {
        const data = await fetchChildrenInternal(taskId, 0, task.totalChildren, true);
        for (const childId of data.newChildIds) {
          pendingUpdatesRef.current.depths[childId] = currentDepth + 1;
          tasksToProcess.push({ id: childId, depth: currentDepth + 1 });
        }
      } catch (err) {
        console.error(`Failed to load children for ${taskId}:`, err);
      }
    }

    if (task.hasCallbacksToLoad) {
      try {
        const data = await fetchCallbacksInternal(taskId, true);
        for (const callbackId of data.allCallbackIds) {
          pendingUpdatesRef.current.depths[callbackId] = currentDepth + 1;
          tasksToProcess.push({ id: callbackId, depth: currentDepth + 1 });
        }
      } catch (err) {
        console.error(`Failed to load callbacks for ${taskId}:`, err);
      }
    }

    for (const { id, depth } of tasksToProcess) {
      const updatedSnapshot = { ...tasksSnapshot, ...pendingUpdatesRef.current.tasks };
      await autoLoadToDepth(id, depth, updatedSnapshot);
    }
  }, [fetchChildrenInternal, fetchCallbacksInternal]);

  const fetchRootTasks = useCallback(async () => {
    setLoading(true);
    setError(null);
    pendingUpdatesRef.current = { tasks: {}, depths: {}, loadingStates: {} };

    try {
      const response = await fetch('/api/tasks/roots');
      const data = await response.json();
      if (data.error) throw new Error(data.error);

      const initialStates = {};
      const initialDepths = {};
      Object.keys(data.tasks).forEach(taskId => {
        initialStates[taskId] = { children: LOADING_STATES.IDLE, callbacks: LOADING_STATES.IDLE };
        initialDepths[taskId] = 0;
      });

      setTasks(data.tasks);
      setLoadingStates(initialStates);
      setTaskDepths(initialDepths);
      setLoading(false);

      for (const taskId of Object.keys(data.tasks)) {
        await autoLoadToDepth(taskId, 0, data.tasks);
      }

      if (flushTimeoutRef.current) {
        clearTimeout(flushTimeoutRef.current);
        flushTimeoutRef.current = null;
      }
      flushPendingUpdates();
    } catch (err) {
      setError(err.message);
      setTasks({});
      setLoading(false);
    }
  }, [autoLoadToDepth, flushPendingUpdates]);

  const fetchChildren = useCallback(async (taskId, page = 0, size = 10) => {
    const currentDepth = taskDepths[taskId] || 0;
    const data = await fetchChildrenInternal(taskId, page, size, false);

    const newDepths = {};
    for (const childId of data.newChildIds) {
      newDepths[childId] = currentDepth + 1;
    }
    setTaskDepths(prev => ({ ...prev, ...newDepths }));

    return data;
  }, [fetchChildrenInternal, taskDepths]);

  const fetchCallbacks = useCallback(async (taskId) => {
    const currentDepth = taskDepths[taskId] || 0;
    const data = await fetchCallbacksInternal(taskId, false);

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
    pendingUpdatesRef.current = { tasks: {}, depths: {}, loadingStates: {} };

    if (task.totalChildren > 0 && !task.childrenLoaded) {
      const data = await fetchChildrenInternal(taskId, 0, task.totalChildren, true);
      for (const childId of data.newChildIds) {
        pendingUpdatesRef.current.depths[childId] = currentDepth + 1;
        const updatedSnapshot = { ...tasks, ...pendingUpdatesRef.current.tasks };
        await autoLoadToDepth(childId, currentDepth + 1, updatedSnapshot);
      }
    }

    if (task.hasCallbacksToLoad) {
      const data = await fetchCallbacksInternal(taskId, true);
      for (const callbackId of data.allCallbackIds) {
        pendingUpdatesRef.current.depths[callbackId] = currentDepth + 1;
        const updatedSnapshot = { ...tasks, ...pendingUpdatesRef.current.tasks };
        await autoLoadToDepth(callbackId, currentDepth + 1, updatedSnapshot);
      }
    }

    if (flushTimeoutRef.current) {
      clearTimeout(flushTimeoutRef.current);
      flushTimeoutRef.current = null;
    }
    flushPendingUpdates();
  }, [tasks, taskDepths, fetchChildrenInternal, fetchCallbacksInternal, autoLoadToDepth, flushPendingUpdates]);

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
