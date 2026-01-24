/**
 * Task Types for MageFlow Graph Visualization
 */

export type TaskType = 'task' | 'chain' | 'swarm' | 'batch_item';

export type TaskStatus = 'pending' | 'active' | 'suspended' | 'interrupted' | 'canceled' | 'completed' | 'failed';

export type LoadingState = 'idle' | 'loading' | 'loaded' | 'error';

export interface TaskDimensions {
  width: number;
  height: number;
  calculatedAt: number;
}

export interface SubtasksPagination {
  currentPage: number;
  pageSize: number;
  totalCount: number;
  loadedPages: Set<number>;
}

export interface Task {
  id: string;
  type: TaskType;
  name: string;
  status: TaskStatus;
  parentId: string | null;

  // Relationships (IDs only, not full objects)
  subtaskIds: string[];
  successCallbackIds: string[];
  errorCallbackIds: string[];

  // Metadata
  kwargs: Record<string, unknown>;
  createdAt: string;

  // Loading states
  loadingState: LoadingState;
  subtasksLoadingState: LoadingState;

  // Pagination for subtasks
  subtasksPagination: SubtasksPagination;

  // Dimensions (calculated by component, stored for layout)
  dimensions: TaskDimensions | null;
}

export interface TaskFromServer {
  id: string;
  type: TaskType;
  name: string;
  status: TaskStatus;
  parent_id: string | null;
  subtask_ids: string[];
  success_callback_ids: string[];
  error_callback_ids: string[];
  kwargs: Record<string, unknown>;
  created_at: string;
}

// Transform server response to client Task
export function transformTask(serverTask: TaskFromServer): Task {
  return {
    id: serverTask.id,
    type: serverTask.type,
    name: serverTask.name,
    status: serverTask.status,
    parentId: serverTask.parent_id,
    subtaskIds: serverTask.subtask_ids,
    successCallbackIds: serverTask.success_callback_ids,
    errorCallbackIds: serverTask.error_callback_ids,
    kwargs: serverTask.kwargs,
    createdAt: serverTask.created_at,
    loadingState: 'loaded',
    subtasksLoadingState: 'idle',
    subtasksPagination: {
      currentPage: 0,
      pageSize: 20,
      totalCount: serverTask.subtask_ids.length,
      loadedPages: new Set(),
    },
    dimensions: null,
  };
}
