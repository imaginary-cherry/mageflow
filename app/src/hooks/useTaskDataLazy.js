import { useState, useCallback, useRef } from 'react';
import { isContainerTask, hasCallbacks } from '../models/TaskModels.js';
import { TaskFactory } from '../models/TaskFactory.js';

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

  const fetchChildrenInternal = useCallback(async (taskId, batch = false) => {
    if (!batch) {
      updateLoadingState(taskId, 'children', LOADING_STATES.LOADING);
    }
    try {
      const response = await fetch(`/api/tasks/${taskId}/children`);
      const data = await response.json();
      if (data?.error) throw new Error(data.error);

      if (data === null || data.children === null) {
        if (!batch) {
          updateLoadingState(taskId, 'children', LOADING_STATES.LOADED);
        } else {
          pendingUpdatesRef.current.loadingStates[taskId] = {
            ...(pendingUpdatesRef.current.loadingStates[taskId] || loadingStates[taskId] || {}),
            children: LOADING_STATES.LOADED,
          };
          scheduleFlush();
        }
        return { newChildIds: [] };
      }

      const transformedChildren = {};
      data.children.forEach(child => {
        const transformed = TaskFactory.transformApiTask(child);
        transformedChildren[transformed.id] = transformed;
      });
      const newChildIds = Object.keys(transformedChildren);

      if (batch) {
        Object.entries(transformedChildren).forEach(([childId, childData]) => {
          pendingUpdatesRef.current.tasks[childId] = childData;
          if (!pendingUpdatesRef.current.loadingStates[childId]) {
            pendingUpdatesRef.current.loadingStates[childId] = { children: LOADING_STATES.IDLE, callbacks: LOADING_STATES.IDLE };
          }
        });

        pendingUpdatesRef.current.loadingStates[taskId] = {
          ...(pendingUpdatesRef.current.loadingStates[taskId] || loadingStates[taskId] || {}),
          children: LOADING_STATES.LOADED,
        };
        scheduleFlush();
      } else {
        setTasks(prev => {
          const updated = { ...prev };
          Object.entries(transformedChildren).forEach(([childId, childData]) => {
            updated[childId] = childData;
          });
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

        updateLoadingState(taskId, 'children', LOADING_STATES.LOADED);
      }

      return { newChildIds };
    } catch (err) {
      if (!batch) {
        updateLoadingState(taskId, 'children', LOADING_STATES.ERROR);
      }
      throw err;
    }
  }, [updateLoadingState, scheduleFlush, loadingStates]);

  const fetchCallbacksInternal = useCallback(async (taskId, batch = false) => {
    if (!batch) {
      updateLoadingState(taskId, 'callbacks', LOADING_STATES.LOADING);
    }
    try {
      const response = await fetch(`/api/tasks/${taskId}/callbacks`);
      const data = await response.json();
      if (data?.error) throw new Error(data.error);

      if (data === null || (data.success_callbacks === null && data.error_callbacks === null)) {
        if (!batch) {
          updateLoadingState(taskId, 'callbacks', LOADING_STATES.LOADED);
        } else {
          pendingUpdatesRef.current.loadingStates[taskId] = {
            ...(pendingUpdatesRef.current.loadingStates[taskId] || loadingStates[taskId] || {}),
            callbacks: LOADING_STATES.LOADED,
          };
          scheduleFlush();
        }
        return { allCallbackIds: [] };
      }

      const successCallbacks = data.success_callbacks || [];
      const errorCallbacks = data.error_callbacks || [];
      const allCallbacks = [...successCallbacks, ...errorCallbacks];
      const transformedCallbacks = {};
      allCallbacks.forEach(cb => {
        const transformed = TaskFactory.transformApiTask(cb);
        transformedCallbacks[transformed.id] = transformed;
      });
      const allCallbackIds = Object.keys(transformedCallbacks);

      if (batch) {
        Object.entries(transformedCallbacks).forEach(([callbackId, callbackData]) => {
          pendingUpdatesRef.current.tasks[callbackId] = callbackData;
          if (!pendingUpdatesRef.current.loadingStates[callbackId]) {
            pendingUpdatesRef.current.loadingStates[callbackId] = { children: LOADING_STATES.IDLE, callbacks: LOADING_STATES.IDLE };
          }
        });

        pendingUpdatesRef.current.loadingStates[taskId] = {
          ...(pendingUpdatesRef.current.loadingStates[taskId] || loadingStates[taskId] || {}),
          callbacks: LOADING_STATES.LOADED,
        };
        scheduleFlush();
      } else {
        setTasks(prev => {
          const updated = { ...prev };
          Object.entries(transformedCallbacks).forEach(([callbackId, callbackData]) => {
            updated[callbackId] = callbackData;
          });
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

      return { allCallbackIds };
    } catch (err) {
      if (!batch) {
        updateLoadingState(taskId, 'callbacks', LOADING_STATES.ERROR);
      }
      throw err;
    }
  }, [updateLoadingState, scheduleFlush, loadingStates]);

  const autoLoadToDepth = useCallback(async (taskId, currentDepth, tasksSnapshot) => {
    if (currentDepth >= MAX_DEPTH) return;

    const task = pendingUpdatesRef.current.tasks[taskId] || tasksSnapshot[taskId];
    if (!task) return;

    const tasksToProcess = [];
    pendingUpdatesRef.current.depths[taskId] = currentDepth;

    const taskLoadingState = pendingUpdatesRef.current.loadingStates[taskId] || loadingStates[taskId] || {};
    const childrenNotLoaded = taskLoadingState.children !== LOADING_STATES.LOADED;
    const callbacksNotLoaded = taskLoadingState.callbacks !== LOADING_STATES.LOADED;

    if (isContainerTask(task) && task.tasks?.length > 0 && childrenNotLoaded) {
      try {
        const data = await fetchChildrenInternal(taskId, true);
        for (const childId of data.newChildIds) {
          pendingUpdatesRef.current.depths[childId] = currentDepth + 1;
          tasksToProcess.push({ id: childId, depth: currentDepth + 1 });
        }
      } catch (err) {
        console.error(`Failed to load children for ${taskId}:`, err);
      }
    }

    if (hasCallbacks(task) && callbacksNotLoaded) {
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
  }, [fetchChildrenInternal, fetchCallbacksInternal, loadingStates]);

  const fetchRootTasks = useCallback(async () => {
    setLoading(true);
    setError(null);
    pendingUpdatesRef.current = { tasks: {}, depths: {}, loadingStates: {} };

    try {
      const response = await fetch('/api/tasks/roots');
      const data = await response.json();
      if (data.error) throw new Error(data.error);

      const transformedTasks = {};
      Object.entries(data.tasks).forEach(([key, apiTask]) => {
        transformedTasks[key] = TaskFactory.transformApiTask(key, apiTask);
      });

      const initialStates = {};
      const initialDepths = {};
      Object.keys(transformedTasks).forEach(taskId => {
        initialStates[taskId] = { children: LOADING_STATES.IDLE, callbacks: LOADING_STATES.IDLE };
        initialDepths[taskId] = 0;
      });

      setTasks(transformedTasks);
      setLoadingStates(initialStates);
      setTaskDepths(initialDepths);
      setLoading(false);

      Promise.all(
        Object.keys(transformedTasks).map(taskId =>
          autoLoadToDepth(taskId, 0, transformedTasks)
        )
      ).then(() => {
        if (flushTimeoutRef.current) {
          clearTimeout(flushTimeoutRef.current);
          flushTimeoutRef.current = null;
        }
        flushPendingUpdates();
      });
    } catch (err) {
      setError(err.message);
      setTasks({});
      setLoading(false);
    }
  }, [autoLoadToDepth, flushPendingUpdates]);

  const fetchChildren = useCallback(async (taskId) => {
    const currentDepth = taskDepths[taskId] || 0;
    const data = await fetchChildrenInternal(taskId, false);

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

    return fetchChildren(taskId);
  }, [tasks, fetchChildren]);

  const loadMore = useCallback(async (taskId) => {
    const task = tasks[taskId];
    if (!task) return;

    const currentDepth = taskDepths[taskId] || 0;
    pendingUpdatesRef.current = { tasks: {}, depths: {}, loadingStates: {} };

    const taskLoadingState = loadingStates[taskId] || {};
    const childrenNotLoaded = taskLoadingState.children !== LOADING_STATES.LOADED;
    const callbacksNotLoaded = taskLoadingState.callbacks !== LOADING_STATES.LOADED;

    if (isContainerTask(task) && task.tasks?.length > 0 && childrenNotLoaded) {
      const data = await fetchChildrenInternal(taskId, true);
      for (const childId of data.newChildIds) {
        pendingUpdatesRef.current.depths[childId] = currentDepth + 1;
        const updatedSnapshot = { ...tasks, ...pendingUpdatesRef.current.tasks };
        await autoLoadToDepth(childId, currentDepth + 1, updatedSnapshot);
      }
    }

    if (hasCallbacks(task) && callbacksNotLoaded) {
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
  }, [tasks, taskDepths, loadingStates, fetchChildrenInternal, fetchCallbacksInternal, autoLoadToDepth, flushPendingUpdates]);

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
