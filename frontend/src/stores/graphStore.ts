/**
 * Normalized Graph Store using Zustand with Immer
 *
 * Key Design Principles:
 * 1. Flat/normalized structure for O(1) lookups and updates
 * 2. Immer for immutable updates without recreation
 * 3. Actions that only modify what's necessary
 * 4. Separate concerns: tasks, edges, UI state
 */

import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import { subscribeWithSelector } from 'zustand/middleware';
import {
  Task,
  TaskStatus,
  TaskDimensions,
  LoadingState,
  Edge,
  UIState,
  Viewport,
  DEFAULT_VIEWPORT,
} from '../types';

// ============================================================================
// Store Interface
// ============================================================================

interface GraphState {
  // Normalized data collections
  tasks: Record<string, Task>;
  edges: Record<string, Edge>;
  rootTaskIds: string[];

  // UI state
  ui: UIState;

  // Computed cache for layout positions
  positions: Record<string, { x: number; y: number }>;
}

interface GraphActions {
  // Task CRUD operations
  setTask: (task: Task) => void;
  setTasks: (tasks: Task[]) => void;
  removeTask: (taskId: string) => void;

  // Task field updates (granular updates)
  updateTaskStatus: (taskId: string, status: TaskStatus) => void;
  updateTaskLoadingState: (taskId: string, state: LoadingState) => void;
  updateTaskSubtasksLoadingState: (taskId: string, state: LoadingState) => void;
  updateTaskDimensions: (taskId: string, dimensions: TaskDimensions) => void;

  // Subtask management
  appendSubtaskIds: (taskId: string, subtaskIds: string[], page: number) => void;
  setSubtaskPage: (taskId: string, page: number) => void;
  setSubtaskTotalCount: (taskId: string, totalCount: number) => void;

  // Edge operations
  setEdge: (edge: Edge) => void;
  setEdges: (edges: Edge[]) => void;
  removeEdge: (edgeId: string) => void;
  removeEdgesForTask: (taskId: string) => void;

  // Root tasks
  setRootTaskIds: (ids: string[]) => void;
  addRootTaskId: (id: string) => void;

  // UI operations
  selectTask: (taskId: string | null) => void;
  toggleNodeExpanded: (taskId: string) => void;
  expandNode: (taskId: string) => void;
  collapseNode: (taskId: string) => void;
  setActiveRoot: (taskId: string | null) => void;
  setViewport: (viewport: Viewport) => void;
  setLoading: (isLoading: boolean) => void;
  setError: (error: string | null) => void;

  // Layout positions
  setPositions: (positions: Record<string, { x: number; y: number }>) => void;
  setPosition: (taskId: string, position: { x: number; y: number }) => void;

  // Batch operations
  reset: () => void;
}

export type GraphStore = GraphState & { actions: GraphActions };

// ============================================================================
// Initial State
// ============================================================================

const initialState: GraphState = {
  tasks: {},
  edges: {},
  rootTaskIds: [],
  ui: {
    selectedTaskId: null,
    expandedNodeIds: new Set(),
    activeRootId: null,
    viewport: DEFAULT_VIEWPORT,
    isLoading: false,
    error: null,
  },
  positions: {},
};

// ============================================================================
// Store Implementation
// ============================================================================

export const useGraphStore = create<GraphStore>()(
  subscribeWithSelector(
    immer((set, get) => ({
      ...initialState,

      actions: {
        // ====================================================================
        // Task CRUD Operations
        // ====================================================================

        setTask: (task) =>
          set((state) => {
            state.tasks[task.id] = task;
          }),

        setTasks: (tasks) =>
          set((state) => {
            for (const task of tasks) {
              state.tasks[task.id] = task;
            }
          }),

        removeTask: (taskId) =>
          set((state) => {
            delete state.tasks[taskId];
            delete state.positions[taskId];
            // Also remove from parent's subtaskIds if applicable
            const task = state.tasks[taskId];
            if (task?.parentId && state.tasks[task.parentId]) {
              const parent = state.tasks[task.parentId];
              parent.subtaskIds = parent.subtaskIds.filter((id) => id !== taskId);
            }
          }),

        // ====================================================================
        // Granular Task Updates
        // ====================================================================

        updateTaskStatus: (taskId, status) =>
          set((state) => {
            if (state.tasks[taskId]) {
              state.tasks[taskId].status = status;
            }
          }),

        updateTaskLoadingState: (taskId, loadingState) =>
          set((state) => {
            if (state.tasks[taskId]) {
              state.tasks[taskId].loadingState = loadingState;
            }
          }),

        updateTaskSubtasksLoadingState: (taskId, loadingState) =>
          set((state) => {
            if (state.tasks[taskId]) {
              state.tasks[taskId].subtasksLoadingState = loadingState;
            }
          }),

        updateTaskDimensions: (taskId, dimensions) =>
          set((state) => {
            if (state.tasks[taskId]) {
              state.tasks[taskId].dimensions = dimensions;
            }
          }),

        // ====================================================================
        // Subtask Pagination
        // ====================================================================

        appendSubtaskIds: (taskId, subtaskIds, page) =>
          set((state) => {
            const task = state.tasks[taskId];
            if (!task) return;

            // Add new subtask IDs (avoid duplicates)
            const existingIds = new Set(task.subtaskIds);
            for (const id of subtaskIds) {
              if (!existingIds.has(id)) {
                task.subtaskIds.push(id);
              }
            }

            // Mark page as loaded
            task.subtasksPagination.loadedPages.add(page);
          }),

        setSubtaskPage: (taskId, page) =>
          set((state) => {
            if (state.tasks[taskId]) {
              state.tasks[taskId].subtasksPagination.currentPage = page;
            }
          }),

        setSubtaskTotalCount: (taskId, totalCount) =>
          set((state) => {
            if (state.tasks[taskId]) {
              state.tasks[taskId].subtasksPagination.totalCount = totalCount;
            }
          }),

        // ====================================================================
        // Edge Operations
        // ====================================================================

        setEdge: (edge) =>
          set((state) => {
            state.edges[edge.id] = edge;
          }),

        setEdges: (edges) =>
          set((state) => {
            for (const edge of edges) {
              state.edges[edge.id] = edge;
            }
          }),

        removeEdge: (edgeId) =>
          set((state) => {
            delete state.edges[edgeId];
          }),

        removeEdgesForTask: (taskId) =>
          set((state) => {
            const edgeIds = Object.keys(state.edges).filter(
              (id) =>
                state.edges[id].source === taskId ||
                state.edges[id].target === taskId
            );
            for (const id of edgeIds) {
              delete state.edges[id];
            }
          }),

        // ====================================================================
        // Root Tasks
        // ====================================================================

        setRootTaskIds: (ids) =>
          set((state) => {
            state.rootTaskIds = ids;
          }),

        addRootTaskId: (id) =>
          set((state) => {
            if (!state.rootTaskIds.includes(id)) {
              state.rootTaskIds.push(id);
            }
          }),

        // ====================================================================
        // UI Operations
        // ====================================================================

        selectTask: (taskId) =>
          set((state) => {
            state.ui.selectedTaskId = taskId;
          }),

        toggleNodeExpanded: (taskId) =>
          set((state) => {
            if (state.ui.expandedNodeIds.has(taskId)) {
              state.ui.expandedNodeIds.delete(taskId);
            } else {
              state.ui.expandedNodeIds.add(taskId);
            }
          }),

        expandNode: (taskId) =>
          set((state) => {
            state.ui.expandedNodeIds.add(taskId);
          }),

        collapseNode: (taskId) =>
          set((state) => {
            state.ui.expandedNodeIds.delete(taskId);
          }),

        setActiveRoot: (taskId) =>
          set((state) => {
            state.ui.activeRootId = taskId;
          }),

        setViewport: (viewport) =>
          set((state) => {
            state.ui.viewport = viewport;
          }),

        setLoading: (isLoading) =>
          set((state) => {
            state.ui.isLoading = isLoading;
          }),

        setError: (error) =>
          set((state) => {
            state.ui.error = error;
          }),

        // ====================================================================
        // Layout Positions
        // ====================================================================

        setPositions: (positions) =>
          set((state) => {
            state.positions = positions;
          }),

        setPosition: (taskId, position) =>
          set((state) => {
            state.positions[taskId] = position;
          }),

        // ====================================================================
        // Reset
        // ====================================================================

        reset: () =>
          set((state) => {
            Object.assign(state, initialState);
            state.ui.expandedNodeIds = new Set();
          }),
      },
    }))
  )
);

// ============================================================================
// Action Helpers (for use outside React components)
// ============================================================================

export const graphActions = () => useGraphStore.getState().actions;

// ============================================================================
// Store Subscriptions (for debugging/logging)
// ============================================================================

if (import.meta.env.DEV) {
  useGraphStore.subscribe(
    (state) => state.tasks,
    (tasks) => {
      console.debug('[GraphStore] Tasks updated:', Object.keys(tasks).length);
    }
  );
}
