import { Task, TaskType, PaginatedChildren } from '@/types/task';
import { TaskClient } from './types';
import { NetworkError, NotFoundError, ServerError } from './errors';

interface TaskFromServer {
  id: string;
  type: string;
  name: string;
  status: string;
  children_ids: string[];
  success_callback_ids: string[];
  error_callback_ids: string[];
  metadata?: Record<string, unknown>;
  created_at: string;
}

export class HttpTaskClient implements TaskClient {
  private readonly baseUrl: string;

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl ?? import.meta.env.VITE_API_URL ?? '';
  }

  private handleResponse(response: Response, context: string): void {
    if (response.ok) {
      return;
    }
    if (response.status === 404) {
      throw new NotFoundError(context, `Not found: ${context}`);
    }
    throw new ServerError(response.status, `Server error ${response.status}: ${response.statusText}`);
  }

  async getRootTaskIds(): Promise<string[]> {
    try {
      const response = await fetch(`${this.baseUrl}/api/workflows/roots`);
      this.handleResponse(response, 'root task IDs');
      const data = await response.json();
      return data.taskIds;
    } catch (err) {
      if (err instanceof NetworkError || err instanceof NotFoundError || err instanceof ServerError) {
        throw err;
      }
      throw new NetworkError('Failed to fetch root task IDs', err);
    }
  }

  async getTask(id: string): Promise<Task | undefined> {
    try {
      const response = await fetch(`${this.baseUrl}/api/tasks/batch`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ taskIds: [id] }),
      });

      this.handleResponse(response, `task ${id}`);

      const tasks: TaskFromServer[] = await response.json();
      if (tasks.length === 0) {
        return undefined;
      }

      return this.mapServerTask(tasks[0]);
    } catch (err) {
      if (err instanceof NetworkError || err instanceof NotFoundError || err instanceof ServerError) {
        throw err;
      }
      throw new NetworkError(`Failed to fetch task ${id}`, err);
    }
  }

  async getTasksBatch(ids: string[]): Promise<Task[]> {
    if (ids.length === 0) {
      return [];
    }

    try {
      const response = await fetch(`${this.baseUrl}/api/tasks/batch`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ taskIds: ids }),
      });

      this.handleResponse(response, 'task batch');

      const serverTasks: TaskFromServer[] = await response.json();
      return serverTasks.map(t => this.mapServerTask(t));
    } catch (err) {
      if (err instanceof NetworkError || err instanceof NotFoundError || err instanceof ServerError) {
        throw err;
      }
      throw new NetworkError('Failed to fetch task batch', err);
    }
  }

  async getChildren(
    taskId: string,
    page = 1,
    limit = 5
  ): Promise<PaginatedChildren> {
    try {
      const response = await fetch(
        `${this.baseUrl}/api/workflows/${taskId}/children?page=${page}&page_size=${limit}`
      );

      this.handleResponse(response, `children of task ${taskId}`);

      const data = await response.json();
      const { taskIds, totalCount, page: responsePage, pageSize } = data;

      const batchResponse = await fetch(`${this.baseUrl}/api/tasks/batch`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ taskIds }),
      });

      this.handleResponse(batchResponse, `child tasks batch for ${taskId}`);

      const serverTasks: TaskFromServer[] = await batchResponse.json();
      const tasks = serverTasks.map(t => this.mapServerTask(t));

      return {
        tasks,
        total: totalCount,
        page: responsePage,
        total_pages: Math.ceil(totalCount / pageSize),
      };
    } catch (err) {
      if (err instanceof NetworkError || err instanceof NotFoundError || err instanceof ServerError) {
        throw err;
      }
      throw new NetworkError(`Failed to fetch children of task ${taskId}`, err);
    }
  }

  async cancelTask(taskId: string): Promise<void> {
    try {
      const response = await fetch(`${this.baseUrl}/api/tasks/${taskId}/cancel`, {
        method: 'POST',
      });

      this.handleResponse(response, `cancel task ${taskId}`);
    } catch (err) {
      if (err instanceof NetworkError || err instanceof NotFoundError || err instanceof ServerError) {
        throw err;
      }
      throw new NetworkError(`Failed to cancel task ${taskId}`, err);
    }
  }

  async pauseTask(taskId: string): Promise<void> {
    try {
      const response = await fetch(`${this.baseUrl}/api/tasks/${taskId}/pause`, {
        method: 'POST',
      });

      this.handleResponse(response, `pause task ${taskId}`);
    } catch (err) {
      if (err instanceof NetworkError || err instanceof NotFoundError || err instanceof ServerError) {
        throw err;
      }
      throw new NetworkError(`Failed to pause task ${taskId}`, err);
    }
  }

  async retryTask(taskId: string): Promise<void> {
    try {
      const response = await fetch(`${this.baseUrl}/api/tasks/${taskId}/retry`, {
        method: 'POST',
      });

      this.handleResponse(response, `retry task ${taskId}`);
    } catch (err) {
      if (err instanceof NetworkError || err instanceof NotFoundError || err instanceof ServerError) {
        throw err;
      }
      throw new NetworkError(`Failed to retry task ${taskId}`, err);
    }
  }

  private mapServerTask(data: TaskFromServer): Task {
    const type = this.mapTaskType(data.type);

    return {
      id: data.id,
      type,
      name: data.name,
      status: data.status as Task['status'],
      children_ids: data.children_ids,
      success_callback_ids: data.success_callback_ids,
      error_callback_ids: data.error_callback_ids,
      metadata: data.metadata,
    };
  }

  private mapTaskType(serverType: string): TaskType {
    switch (serverType) {
      case 'TaskSignature':
        return 'simple';
      case 'ChainTaskSignature':
        return 'chain';
      case 'SwarmTaskSignature':
        return 'swarm';
      default:
        return 'simple';
    }
  }
}
