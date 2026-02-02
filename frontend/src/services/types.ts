import { Task, PaginatedChildren } from '@/types/task';

export interface TaskClient {
  getRootTaskIds(): Promise<string[]>;
  getTask(id: string): Promise<Task | undefined>;
  getTasksMap(): Promise<Record<string, Task>>;
  getChildren(taskId: string, page?: number, limit?: number): Promise<PaginatedChildren>;
  cancelTask(taskId: string): Promise<void>;
  pauseTask(taskId: string): Promise<void>;
  retryTask(taskId: string): Promise<void>;
}
