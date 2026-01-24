/**
 * Progressive Loader Hook
 *
 * Implements the progressive loading strategy:
 * 1. Root tasks first
 * 2. Callbacks (BFS from root)
 * 3. Subtasks (on-demand with pagination)
 * 4. Nested subtasks (recursive)
 */

import { useCallback, useRef, useEffect } from 'react';
import { useGraphStore } from '../stores/graphStore';
import { api } from '../api/client';
import {
  createSuccessEdge,
  createErrorEdge,
  createSubtaskEdge,
  createSequenceEdge,
} from '../types';

// ============================================================================
// Types
// ============================================================================

interface LoaderState {
  loadedTaskIds: Set<string>;
  loadedCallbacks: Set<string>; // "callbacks:{taskId}"
  loadedSubtasks: Set<string>; // "subtasks:{taskId}:{page}"
  pendingCallbackTaskIds: Set<string>;
  loadingPromises: Map<string, Promise<void>>;
}

interface UseProgressiveLoaderResult {
  loadRoots: () => Promise<string[]>;
  loadCallbacks: (taskId: string) => Promise<void>;
  loadSubtasks: (taskId: string, page?: number, pageSize?: number) => Promise<void>;
  loadTaskTree: (taskId: string, depth?: number) => Promise<void>;
  isLoading: boolean;
  reset: () => void;
}

// ============================================================================
// Constants
// ============================================================================

const DEFAULT_PAGE_SIZE = 20;
const CALLBACK_LOAD_DELAY_MS = 50;
const MAX_CONCURRENT_LOADS = 5;

// ============================================================================
// Hook Implementation
// ============================================================================

export function useProgressiveLoader(): UseProgressiveLoaderResult {
  const actions = useGraphStore((state) => state.actions);
  const tasks = useGraphStore((state) => state.tasks);

  const stateRef = useRef<LoaderState>({
    loadedTaskIds: new Set(),
    loadedCallbacks: new Set(),
    loadedSubtasks: new Set(),
    pendingCallbackTaskIds: new Set(),
    loadingPromises: new Map(),
  });

  const isLoadingRef = useRef(false);

  // ==========================================================================
  // Phase 1: Load Root Tasks
  // ==========================================================================

  const loadRoots = useCallback(async (): Promise<string[]> => {
    const state = stateRef.current;

    actions.setLoading(true);
    isLoadingRef.current = true;

    try {
      // Fetch root task IDs
      const rootIds = await api.getRootTaskIds();

      if (rootIds.length === 0) {
        actions.setRootTaskIds([]);
        return [];
      }

      // Fetch root task details
      const rootTasks = await api.getTasksBatch(rootIds);

      // Add to store
      actions.setTasks(rootTasks);
      actions.setRootTaskIds(rootIds);

      // Mark as loaded and queue for callback loading
      rootIds.forEach((id) => {
        state.loadedTaskIds.add(id);
        state.pendingCallbackTaskIds.add(id);
      });

      // Set first root as active
      if (rootIds.length > 0) {
        actions.setActiveRoot(rootIds[0]);
      }

      return rootIds;
    } catch (error) {
      actions.setError(`Failed to load root tasks: ${error}`);
      throw error;
    } finally {
      actions.setLoading(false);
      isLoadingRef.current = false;
    }
  }, [actions]);

  // ==========================================================================
  // Phase 2: Load Callbacks (BFS)
  // ==========================================================================

  const loadCallbacks = useCallback(
    async (taskId: string): Promise<void> => {
      const state = stateRef.current;
      const cacheKey = `callbacks:${taskId}`;

      // Skip if already loaded or loading
      if (state.loadedCallbacks.has(cacheKey)) return;

      const existingPromise = state.loadingPromises.get(cacheKey);
      if (existingPromise) return existingPromise;

      const loadPromise = (async () => {
        try {
          const task = tasks[taskId];
          if (!task) {
            // Task not in store yet, fetch it first
            const [fetchedTask] = await api.getTasksBatch([taskId]);
            if (fetchedTask) {
              actions.setTask(fetchedTask);
              state.loadedTaskIds.add(taskId);
            } else {
              return;
            }
          }

          const currentTask = tasks[taskId] ?? (await api.getTask(taskId));

          // Collect all callback IDs
          const callbackIds = [
            ...currentTask.successCallbackIds,
            ...currentTask.errorCallbackIds,
          ].filter((id) => !state.loadedTaskIds.has(id));

          if (callbackIds.length === 0) {
            state.loadedCallbacks.add(cacheKey);
            return;
          }

          // Batch load callback tasks
          const callbackTasks = await api.getTasksBatch(callbackIds);
          actions.setTasks(callbackTasks);

          // Create edges
          const edges = [
            ...currentTask.successCallbackIds.map((targetId) =>
              createSuccessEdge(taskId, targetId)
            ),
            ...currentTask.errorCallbackIds.map((targetId) =>
              createErrorEdge(taskId, targetId)
            ),
          ];
          actions.setEdges(edges);

          // Mark loaded and queue for their own callback loading
          callbackIds.forEach((id) => {
            state.loadedTaskIds.add(id);
            state.pendingCallbackTaskIds.add(id);
          });

          state.loadedCallbacks.add(cacheKey);
        } catch (error) {
          console.error(`Failed to load callbacks for ${taskId}:`, error);
        } finally {
          state.loadingPromises.delete(cacheKey);
        }
      })();

      state.loadingPromises.set(cacheKey, loadPromise);
      return loadPromise;
    },
    [tasks, actions]
  );

  // ==========================================================================
  // Phase 3: Load Subtasks with Pagination
  // ==========================================================================

  const loadSubtasks = useCallback(
    async (
      taskId: string,
      page: number = 0,
      pageSize: number = DEFAULT_PAGE_SIZE
    ): Promise<void> => {
      const state = stateRef.current;
      const cacheKey = `subtasks:${taskId}:${page}`;

      // Skip if already loaded
      if (state.loadedSubtasks.has(cacheKey)) return;

      const existingPromise = state.loadingPromises.get(cacheKey);
      if (existingPromise) return existingPromise;

      const loadPromise = (async () => {
        try {
          actions.updateTaskSubtasksLoadingState(taskId, 'loading');

          // Fetch paginated subtask IDs
          const response = await api.getTaskSubtasks(taskId, { page, pageSize });

          // Update total count
          actions.setSubtaskTotalCount(taskId, response.totalCount);

          if (response.taskIds.length === 0) {
            actions.updateTaskSubtasksLoadingState(taskId, 'loaded');
            state.loadedSubtasks.add(cacheKey);
            return;
          }

          // Batch load subtask details
          const subtaskDetails = await api.getTasksBatch(response.taskIds);

          // Update subtasks with parentId
          const subtasksWithParent = subtaskDetails.map((task) => ({
            ...task,
            parentId: taskId,
          }));
          actions.setTasks(subtasksWithParent);

          // Append subtask IDs to parent
          actions.appendSubtaskIds(taskId, response.taskIds, page);

          // Create edges
          const edges = response.taskIds.map((subtaskId) =>
            createSubtaskEdge(taskId, subtaskId)
          );

          // For chains, also create sequence edges
          const task = tasks[taskId];
          if (task?.type === 'chain') {
            const startIdx = page * pageSize;
            for (let i = 1; i < response.taskIds.length; i++) {
              edges.push(
                createSequenceEdge(response.taskIds[i - 1], response.taskIds[i])
              );
            }
            // Connect to previous page's last item
            if (page > 0 && task.subtaskIds.length > startIdx) {
              const prevLastIdx = startIdx - 1;
              if (prevLastIdx >= 0 && task.subtaskIds[prevLastIdx]) {
                edges.push(
                  createSequenceEdge(task.subtaskIds[prevLastIdx], response.taskIds[0])
                );
              }
            }
          }

          actions.setEdges(edges);

          // Mark subtasks as loaded
          response.taskIds.forEach((id) => {
            state.loadedTaskIds.add(id);
          });

          // Check subtasks for external callbacks
          for (const subtask of subtaskDetails) {
            const hasExternalCallbacks =
              subtask.successCallbackIds.some(
                (cbId) => !isDescendantOf(cbId, taskId, tasks)
              ) ||
              subtask.errorCallbackIds.some(
                (cbId) => !isDescendantOf(cbId, taskId, tasks)
              );

            if (hasExternalCallbacks) {
              state.pendingCallbackTaskIds.add(subtask.id);
            }
          }

          state.loadedSubtasks.add(cacheKey);
          actions.updateTaskSubtasksLoadingState(taskId, 'loaded');
        } catch (error) {
          console.error(`Failed to load subtasks for ${taskId}:`, error);
          actions.updateTaskSubtasksLoadingState(taskId, 'error');
        } finally {
          state.loadingPromises.delete(cacheKey);
        }
      })();

      state.loadingPromises.set(cacheKey, loadPromise);
      return loadPromise;
    },
    [tasks, actions]
  );

  // ==========================================================================
  // Phase 4: Load Full Task Tree (Recursive)
  // ==========================================================================

  const loadTaskTree = useCallback(
    async (taskId: string, depth: number = 2): Promise<void> => {
      if (depth <= 0) return;

      // Load callbacks first
      await loadCallbacks(taskId);

      const task = tasks[taskId];
      if (!task) return;

      // If it's a container task (swarm/chain), load first page of subtasks
      if (task.type === 'swarm' || task.type === 'chain') {
        await loadSubtasks(taskId, 0);

        // Recursively load subtask trees
        if (depth > 1) {
          const currentTask = useGraphStore.getState().tasks[taskId];
          if (currentTask) {
            const subtaskPromises = currentTask.subtaskIds
              .slice(0, MAX_CONCURRENT_LOADS)
              .map((subtaskId) => loadTaskTree(subtaskId, depth - 1));
            await Promise.all(subtaskPromises);
          }
        }
      }
    },
    [tasks, loadCallbacks, loadSubtasks]
  );

  // ==========================================================================
  // BFS Processor for Pending Callbacks
  // ==========================================================================

  useEffect(() => {
    const state = stateRef.current;

    const processPending = async () => {
      while (state.pendingCallbackTaskIds.size > 0) {
        // Take batch of pending IDs
        const batch = Array.from(state.pendingCallbackTaskIds).slice(
          0,
          MAX_CONCURRENT_LOADS
        );
        batch.forEach((id) => state.pendingCallbackTaskIds.delete(id));

        // Load callbacks in parallel
        await Promise.all(batch.map((id) => loadCallbacks(id)));

        // Small delay to prevent overwhelming
        await new Promise((resolve) => setTimeout(resolve, CALLBACK_LOAD_DELAY_MS));
      }
    };

    // Start processing if there are pending items
    if (state.pendingCallbackTaskIds.size > 0) {
      processPending();
    }
  }, [loadCallbacks]);

  // ==========================================================================
  // Reset
  // ==========================================================================

  const reset = useCallback(() => {
    const state = stateRef.current;
    state.loadedTaskIds.clear();
    state.loadedCallbacks.clear();
    state.loadedSubtasks.clear();
    state.pendingCallbackTaskIds.clear();
    state.loadingPromises.clear();
    isLoadingRef.current = false;
    actions.reset();
  }, [actions]);

  return {
    loadRoots,
    loadCallbacks,
    loadSubtasks,
    loadTaskTree,
    isLoading: isLoadingRef.current,
    reset,
  };
}

// ============================================================================
// Helper Functions
// ============================================================================

function isDescendantOf(
  taskId: string,
  parentId: string,
  tasks: Record<string, any>
): boolean {
  let current = tasks[taskId];
  const visited = new Set<string>();

  while (current) {
    if (visited.has(current.id)) break;
    visited.add(current.id);

    if (current.parentId === parentId) return true;
    if (!current.parentId) return false;
    current = tasks[current.parentId];
  }
  return false;
}
