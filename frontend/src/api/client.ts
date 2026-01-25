/**
 * API Client with Batching and Caching
 *
 * Features:
 * 1. Automatic request batching (combine multiple task requests)
 * 2. In-memory cache with TTL
 * 3. Request deduplication
 * 4. Retry with exponential backoff
 */

import { Task, TaskFromServer, transformTask } from '../types';

// ============================================================================
// Configuration
// ============================================================================

const getApiBase = (): string => {
  if (typeof process !== 'undefined' && process.env?.VITE_API_URL) {
    return process.env.VITE_API_URL;
  }
  if (typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_URL) {
    return import.meta.env.VITE_API_URL;
  }
  return '/api';
};

const API_BASE = getApiBase();
const BATCH_SIZE = 50;
const CACHE_TTL_MS = 30_000; // 30 seconds
const MAX_RETRIES = 3;
const RETRY_DELAY_MS = 1000;
const BATCH_DELAY_MS = 10; // Wait before executing batch

// ============================================================================
// Types
// ============================================================================

interface CacheEntry<T> {
  data: T;
  timestamp: number;
}

interface SubtasksResponse {
  taskIds: string[];
  totalCount: number;
  page: number;
  pageSize: number;
}

interface RootTasksResponse {
  taskIds: string[];
}

// ============================================================================
// Cache Implementation
// ============================================================================

class Cache<T> {
  private store = new Map<string, CacheEntry<T>>();
  private ttl: number;

  constructor(ttlMs: number = CACHE_TTL_MS) {
    this.ttl = ttlMs;
  }

  get(key: string): T | null {
    const entry = this.store.get(key);
    if (!entry) return null;

    if (Date.now() - entry.timestamp > this.ttl) {
      this.store.delete(key);
      return null;
    }

    return entry.data;
  }

  set(key: string, data: T): void {
    this.store.set(key, { data, timestamp: Date.now() });
  }

  delete(key: string): void {
    this.store.delete(key);
  }

  clear(): void {
    this.store.clear();
  }

  has(key: string): boolean {
    return this.get(key) !== null;
  }
}

// ============================================================================
// Batch Queue Implementation
// ============================================================================

class BatchQueue {
  private queue: string[] = [];
  private pending: Map<string, { resolve: (task: Task) => void; reject: (err: Error) => void }[]> = new Map();
  private timer: ReturnType<typeof setTimeout> | null = null;
  private fetcher: (ids: string[]) => Promise<Task[]>;

  constructor(fetcher: (ids: string[]) => Promise<Task[]>) {
    this.fetcher = fetcher;
  }

  add(taskId: string): Promise<Task> {
    return new Promise((resolve, reject) => {
      // Add to pending callbacks
      if (!this.pending.has(taskId)) {
        this.pending.set(taskId, []);
        this.queue.push(taskId);
      }
      this.pending.get(taskId)!.push({ resolve, reject });

      // Schedule batch execution
      this.scheduleBatch();
    });
  }

  private scheduleBatch(): void {
    if (this.timer) return;

    this.timer = setTimeout(async () => {
      this.timer = null;
      await this.executeBatch();
    }, BATCH_DELAY_MS);
  }

  private async executeBatch(): Promise<void> {
    if (this.queue.length === 0) return;

    // Take items from queue
    const batch = this.queue.splice(0, BATCH_SIZE);
    const pendingCallbacks = new Map(
      batch.map(id => [id, this.pending.get(id)!])
    );
    batch.forEach(id => this.pending.delete(id));

    try {
      const tasks = await this.fetcher(batch);
      const taskMap = new Map(tasks.map(t => [t.id, t]));

      // Resolve promises
      for (const [id, callbacks] of pendingCallbacks) {
        const task = taskMap.get(id);
        if (task) {
          callbacks.forEach(cb => cb.resolve(task));
        } else {
          callbacks.forEach(cb => cb.reject(new Error(`Task ${id} not found`)));
        }
      }
    } catch (error) {
      // Reject all promises on error
      for (const [, callbacks] of pendingCallbacks) {
        callbacks.forEach(cb => cb.reject(error as Error));
      }
    }

    // Continue if more items in queue
    if (this.queue.length > 0) {
      this.scheduleBatch();
    }
  }
}

// ============================================================================
// API Client Class
// ============================================================================

export class APIClient {
  private cache = new Cache<Task>();
  private batchQueue: BatchQueue;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private inflightRequests = new Map<string, Promise<any>>();
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl;
    this.batchQueue = new BatchQueue((ids) => this.fetchTasksBatch(ids));
  }

  // ==========================================================================
  // HTTP Helpers
  // ==========================================================================

  private async fetch<T>(
    url: string,
    options: RequestInit = {}
  ): Promise<T> {
    const response = await fetch(`${this.baseUrl}${url}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  private async fetchWithRetry<T>(
    url: string,
    options: RequestInit = {},
    retries: number = MAX_RETRIES
  ): Promise<T> {
    let lastError: Error | null = null;

    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        return await this.fetch<T>(url, options);
      } catch (error) {
        lastError = error as Error;
        if (attempt < retries) {
          await this.delay(RETRY_DELAY_MS * Math.pow(2, attempt));
        }
      }
    }

    throw lastError;
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  // Deduplicate concurrent requests for the same resource
  private async deduplicatedFetch<T>(
    key: string,
    fetcher: () => Promise<T>
  ): Promise<T> {
    if (this.inflightRequests.has(key)) {
      return this.inflightRequests.get(key)!;
    }

    const promise = fetcher().finally(() => {
      this.inflightRequests.delete(key);
    });

    this.inflightRequests.set(key, promise);
    return promise;
  }

  // ==========================================================================
  // Root Tasks
  // ==========================================================================

  async getRootTaskIds(): Promise<string[]> {
    return this.deduplicatedFetch('roots', async () => {
      const response = await this.fetchWithRetry<RootTasksResponse>(
        '/workflows/roots'
      );
      return response.taskIds;
    });
  }

  // ==========================================================================
  // Single Task (uses batch queue)
  // ==========================================================================

  async getTask(taskId: string): Promise<Task> {
    // Check cache first
    const cached = this.cache.get(taskId);
    if (cached) return cached;

    // Add to batch queue
    const task = await this.batchQueue.add(taskId);
    this.cache.set(taskId, task);
    return task;
  }

  // ==========================================================================
  // Batch Tasks
  // ==========================================================================

  async getTasksBatch(taskIds: string[]): Promise<Task[]> {
    if (taskIds.length === 0) return [];

    // Separate cached and uncached
    const cached: Task[] = [];
    const uncachedIds: string[] = [];

    for (const id of taskIds) {
      const cachedTask = this.cache.get(id);
      if (cachedTask) {
        cached.push(cachedTask);
      } else {
        uncachedIds.push(id);
      }
    }

    if (uncachedIds.length === 0) {
      return cached;
    }

    // Fetch uncached in batches
    const fetched: Task[] = [];
    for (let i = 0; i < uncachedIds.length; i += BATCH_SIZE) {
      const batchIds = uncachedIds.slice(i, i + BATCH_SIZE);
      const batchTasks = await this.fetchTasksBatch(batchIds);
      fetched.push(...batchTasks);
    }

    // Cache fetched tasks
    for (const task of fetched) {
      this.cache.set(task.id, task);
    }

    return [...cached, ...fetched];
  }

  private async fetchTasksBatch(taskIds: string[]): Promise<Task[]> {
    const response = await this.fetchWithRetry<TaskFromServer[]>(
      '/tasks/batch',
      {
        method: 'POST',
        body: JSON.stringify({ taskIds }),
      }
    );

    return response.map(transformTask);
  }

  // ==========================================================================
  // Subtasks with Pagination
  // ==========================================================================

  async getTaskSubtasks(
    taskId: string,
    options: { page: number; pageSize: number }
  ): Promise<SubtasksResponse> {
    const { page, pageSize } = options;
    const cacheKey = `subtasks:${taskId}:${page}:${pageSize}`;

    return this.deduplicatedFetch(cacheKey, async () => {
      const response = await this.fetchWithRetry<SubtasksResponse>(
        `/workflows/${taskId}/children?page=${page}&pageSize=${pageSize}`
      );
      return response;
    });
  }

  // ==========================================================================
  // Callbacks
  // ==========================================================================

  async getTaskCallbacks(taskId: string): Promise<{
    successCallbackIds: string[];
    errorCallbackIds: string[];
  }> {
    const cacheKey = `callbacks:${taskId}`;

    return this.deduplicatedFetch(cacheKey, async () => {
      const response = await this.fetchWithRetry<{
        success_callback_ids: string[];
        error_callback_ids: string[];
      } | null>(`/workflows/${taskId}/callbacks`);

      if (!response) {
        return {
          successCallbackIds: [],
          errorCallbackIds: [],
        };
      }

      return {
        successCallbackIds: response.success_callback_ids,
        errorCallbackIds: response.error_callback_ids,
      };
    });
  }

  // ==========================================================================
  // Cache Management
  // ==========================================================================

  invalidateTask(taskId: string): void {
    this.cache.delete(taskId);
  }

  invalidateAll(): void {
    this.cache.clear();
  }

  // ==========================================================================
  // Health Check
  // ==========================================================================

  async healthCheck(): Promise<boolean> {
    try {
      await this.fetch('/health');
      return true;
    } catch {
      return false;
    }
  }
}

// ============================================================================
// Singleton Export
// ============================================================================

export const api = new APIClient();

// ============================================================================
// Hook for API Access
// ============================================================================

export function useAPI(): APIClient {
  return api;
}
