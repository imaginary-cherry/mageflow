import { Task, TaskType, PaginatedChildren } from '@/types/task';
import { TaskClient } from './types';

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
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  async getRootTaskIds(): Promise<string[]> {
    const response = await fetch(`${this.baseUrl}/api/workflows/roots`);
    if (!response.ok) {
      throw new Error(`Failed to fetch root task IDs: ${response.status}`);
    }
    const data = await response.json();
    return data.taskIds;
  }

  async getTask(id: string): Promise<Task | undefined> {
    const response = await fetch(`${this.baseUrl}/api/tasks/batch`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ taskIds: [id] }),
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch task: ${response.status}`);
    }

    const tasks: TaskFromServer[] = await response.json();
    if (tasks.length === 0) {
      return undefined;
    }

    return this.mapServerTask(tasks[0]);
  }

  async getTasksMap(): Promise<Record<string, Task>> {
    return {};
  }

  async getChildren(
    taskId: string,
    page = 1,
    limit = 5
  ): Promise<PaginatedChildren> {
    const response = await fetch(
      `${this.baseUrl}/api/workflows/${taskId}/children?page=${page}&page_size=${limit}`
    );

    if (!response.ok) {
      throw new Error(`Failed to fetch children: ${response.status}`);
    }

    const data = await response.json();
    const { taskIds, totalCount, page: responsePage, pageSize } = data;

    const batchResponse = await fetch(`${this.baseUrl}/api/tasks/batch`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ taskIds }),
    });

    if (!batchResponse.ok) {
      throw new Error(`Failed to fetch child tasks: ${batchResponse.status}`);
    }

    const serverTasks: TaskFromServer[] = await batchResponse.json();
    const tasks = serverTasks.map(t => this.mapServerTask(t));

    return {
      tasks,
      total: totalCount,
      page: responsePage,
      total_pages: Math.ceil(totalCount / pageSize),
    };
  }

  async cancelTask(taskId: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/api/tasks/${taskId}/cancel`, {
      method: 'POST',
    });

    if (!response.ok) {
      throw new Error(`Failed to cancel task: ${response.status}`);
    }
  }

  async pauseTask(taskId: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/api/tasks/${taskId}/pause`, {
      method: 'POST',
    });

    if (!response.ok) {
      throw new Error(`Failed to pause task: ${response.status}`);
    }
  }

  async retryTask(taskId: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/api/tasks/${taskId}/retry`, {
      method: 'POST',
    });

    if (!response.ok) {
      throw new Error(`Failed to retry task: ${response.status}`);
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
