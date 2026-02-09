import { Task, PaginatedChildren } from '@/types/task';
import { TaskClient } from './types';
import { mockTasks, rootTaskIds } from '@/data/mockTasks';

const DEFAULT_PAGE_LIMIT = 5;

export class MockTaskClient implements TaskClient {
  async getRootTaskIds(): Promise<string[]> {
    return Promise.resolve([...rootTaskIds]);
  }

  async getTask(id: string): Promise<Task | undefined> {
    return Promise.resolve(mockTasks[id]);
  }

  async getTasksMap(): Promise<Record<string, Task>> {
    return Promise.resolve({ ...mockTasks });
  }

  async getChildren(taskId: string, page = 1, limit = DEFAULT_PAGE_LIMIT): Promise<PaginatedChildren> {
    const task = mockTasks[taskId];
    if (!task) {
      return Promise.resolve({ tasks: [], total: 0, page: 1, total_pages: 0 });
    }

    const childIds = task.children_ids;
    const total = childIds.length;
    const total_pages = Math.ceil(total / limit);
    const startIndex = (page - 1) * limit;
    const paginatedIds = childIds.slice(startIndex, startIndex + limit);
    const tasks = paginatedIds.map(id => mockTasks[id]).filter((t): t is Task => !!t);

    return Promise.resolve({ tasks, total, page, total_pages });
  }

  async cancelTask(taskId: string): Promise<void> {
    console.log('Cancel task:', taskId);
    return Promise.resolve();
  }

  async pauseTask(taskId: string): Promise<void> {
    console.log('Pause task:', taskId);
    return Promise.resolve();
  }

  async retryTask(taskId: string): Promise<void> {
    console.log('Retry task:', taskId);
    return Promise.resolve();
  }
}
