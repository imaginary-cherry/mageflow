export type TaskType = 'simple' | 'chain' | 'swarm';

export type TaskStatus = 
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'paused';

export interface Task {
  id: string;
  type: TaskType;
  name: string;
  status: TaskStatus;
  children_ids: string[];
  success_callback_ids: string[];
  error_callback_ids: string[];
  metadata?: Record<string, unknown>;
}

export interface PaginatedChildren {
  tasks: Task[];
  total: number;
  page: number;
  total_pages: number;
}

export interface TaskNodeData extends Record<string, unknown> {
  task: Task;
  onTaskClick?: (task: Task) => void;
}
