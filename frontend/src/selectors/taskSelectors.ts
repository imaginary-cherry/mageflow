/**
 * Task Selectors
 *
 * Memoized selectors that derive data from the store.
 * Each selector only triggers re-renders when its specific data changes.
 */

import { useMemo } from 'react';
import { shallow } from 'zustand/shallow';
import { useGraphStore } from '../stores/graphStore';
import { Task, TaskStatus } from '../types';

// ============================================================================
// Single Task Selectors
// ============================================================================

/**
 * Get a single task by ID
 * Only re-renders when THIS task changes
 */
export function useTask(taskId: string | null): Task | null {
  return useGraphStore(
    (state) => (taskId ? state.tasks[taskId] ?? null : null),
    shallow
  );
}

/**
 * Get task status only
 * Useful when you only care about status changes
 */
export function useTaskStatus(taskId: string): TaskStatus | null {
  return useGraphStore((state) => state.tasks[taskId]?.status ?? null);
}

/**
 * Get task type
 */
export function useTaskType(taskId: string): Task['type'] | null {
  return useGraphStore((state) => state.tasks[taskId]?.type ?? null);
}

/**
 * Get task dimensions
 */
export function useTaskDimensions(taskId: string): Task['dimensions'] {
  return useGraphStore((state) => state.tasks[taskId]?.dimensions ?? null);
}

/**
 * Get task position from layout
 */
export function useTaskPosition(taskId: string): { x: number; y: number } | null {
  return useGraphStore((state) => state.positions[taskId] ?? null);
}

// ============================================================================
// Relationship Selectors
// ============================================================================

/**
 * Get subtask IDs only (not full task objects)
 * Prevents re-render when subtask data changes
 */
export function useSubtaskIds(taskId: string): string[] {
  return useGraphStore(
    (state) => state.tasks[taskId]?.subtaskIds ?? [],
    shallow
  );
}

/**
 * Get callback IDs
 */
export function useCallbackIds(taskId: string): {
  successCallbackIds: string[];
  errorCallbackIds: string[];
} {
  return useGraphStore(
    (state) => ({
      successCallbackIds: state.tasks[taskId]?.successCallbackIds ?? [],
      errorCallbackIds: state.tasks[taskId]?.errorCallbackIds ?? [],
    }),
    shallow
  );
}

/**
 * Get parent task ID
 */
export function useParentId(taskId: string): string | null {
  return useGraphStore((state) => state.tasks[taskId]?.parentId ?? null);
}

// ============================================================================
// Pagination Selectors
// ============================================================================

/**
 * Get subtask pagination state
 */
export function useSubtaskPagination(taskId: string) {
  return useGraphStore(
    (state) => state.tasks[taskId]?.subtasksPagination ?? null,
    shallow
  );
}

/**
 * Get visible subtasks for current page
 * Returns full task objects for the current page only
 */
export function useVisibleSubtasks(taskId: string): Task[] {
  const task = useTask(taskId);
  const allTasks = useGraphStore((state) => state.tasks);

  return useMemo(() => {
    if (!task) return [];

    const { currentPage, pageSize } = task.subtasksPagination;
    const startIdx = currentPage * pageSize;
    const endIdx = startIdx + pageSize;

    // Get IDs for current page
    const pageIds = task.subtaskIds.slice(startIdx, endIdx);

    // Return full task objects
    return pageIds.map((id) => allTasks[id]).filter(Boolean);
  }, [
    task?.subtaskIds,
    task?.subtasksPagination.currentPage,
    task?.subtasksPagination.pageSize,
    allTasks,
  ]);
}

/**
 * Check if a page is loaded
 */
export function useIsPageLoaded(taskId: string, page: number): boolean {
  return useGraphStore(
    (state) => state.tasks[taskId]?.subtasksPagination.loadedPages.has(page) ?? false
  );
}

// ============================================================================
// Loading State Selectors
// ============================================================================

/**
 * Get task loading state
 */
export function useTaskLoadingState(taskId: string): Task['loadingState'] {
  return useGraphStore(
    (state) => state.tasks[taskId]?.loadingState ?? 'idle'
  );
}

/**
 * Get subtasks loading state
 */
export function useSubtasksLoadingState(taskId: string): Task['subtasksLoadingState'] {
  return useGraphStore(
    (state) => state.tasks[taskId]?.subtasksLoadingState ?? 'idle'
  );
}

// ============================================================================
// Collection Selectors
// ============================================================================

/**
 * Get all root task IDs
 */
export function useRootTaskIds(): string[] {
  return useGraphStore((state) => state.rootTaskIds, shallow);
}

/**
 * Get all task IDs (for iteration)
 */
export function useAllTaskIds(): string[] {
  return useGraphStore((state) => Object.keys(state.tasks), shallow);
}

/**
 * Get task count
 */
export function useTaskCount(): number {
  return useGraphStore((state) => Object.keys(state.tasks).length);
}

/**
 * Check if task exists
 */
export function useTaskExists(taskId: string): boolean {
  return useGraphStore((state) => taskId in state.tasks);
}

// ============================================================================
// Filtered Selectors
// ============================================================================

/**
 * Get tasks by status
 */
export function useTasksByStatus(status: TaskStatus): Task[] {
  return useGraphStore(
    (state) =>
      Object.values(state.tasks).filter((task) => task.status === status),
    shallow
  );
}

/**
 * Get tasks by type
 */
export function useTasksByType(type: Task['type']): Task[] {
  return useGraphStore(
    (state) =>
      Object.values(state.tasks).filter((task) => task.type === type),
    shallow
  );
}

// ============================================================================
// Graph Traversal Selectors
// ============================================================================

/**
 * Get all descendant IDs for a task (recursive)
 */
export function useDescendantIds(taskId: string): string[] {
  const tasks = useGraphStore((state) => state.tasks);

  return useMemo(() => {
    const descendants: string[] = [];
    const queue = [taskId];
    const visited = new Set<string>();

    while (queue.length > 0) {
      const currentId = queue.shift()!;
      if (visited.has(currentId)) continue;
      visited.add(currentId);

      const task = tasks[currentId];
      if (!task) continue;

      for (const subtaskId of task.subtaskIds) {
        descendants.push(subtaskId);
        queue.push(subtaskId);
      }
    }

    return descendants;
  }, [taskId, tasks]);
}

/**
 * Get all ancestor IDs for a task (up to root)
 */
export function useAncestorIds(taskId: string): string[] {
  const tasks = useGraphStore((state) => state.tasks);

  return useMemo(() => {
    const ancestors: string[] = [];
    let currentId = taskId;

    while (true) {
      const task = tasks[currentId];
      if (!task?.parentId) break;
      ancestors.push(task.parentId);
      currentId = task.parentId;
    }

    return ancestors;
  }, [taskId, tasks]);
}

/**
 * Check if a task is a descendant of another
 */
export function useIsDescendantOf(taskId: string, potentialAncestorId: string): boolean {
  const ancestors = useAncestorIds(taskId);
  return ancestors.includes(potentialAncestorId);
}
