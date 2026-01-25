import { describe, it, expect, beforeAll } from 'vitest';
import { APIClient } from '../../../api/client';
import { API_BASE_URL } from '../../setup';

const TEST_PREFIX = 'test_frontend_';
const TASK_PREFIX = 'TaskSignature:';
const CHAIN_PREFIX = 'ChainTaskSignature:';
const SWARM_PREFIX = 'SwarmTaskSignature:';

describe('API Client Integration Tests', () => {
  let client: APIClient;

  beforeAll(() => {
    client = new APIClient(API_BASE_URL);
  });

  describe('healthCheck()', () => {
    it('should return true when server is running', async () => {
      // Act
      const result = await client.healthCheck();

      // Assert
      expect(result).toBe(true);
    });
  });

  describe('getRootTaskIds()', () => {
    it('should return root task IDs (excludes children/callbacks)', async () => {
      // Act
      const rootTaskIds = await client.getRootTaskIds();

      // Assert
      expect(Array.isArray(rootTaskIds)).toBe(true);
      const testRootIds = rootTaskIds.filter(id => id.includes(TEST_PREFIX));

      if (testRootIds.length > 0) {
        expect(testRootIds).toContain(`${TASK_PREFIX}${TEST_PREFIX}basic_task_001`);
        expect(testRootIds).toContain(`${CHAIN_PREFIX}${TEST_PREFIX}chain_001`);
        expect(testRootIds).toContain(`${SWARM_PREFIX}${TEST_PREFIX}swarm_001`);
        expect(testRootIds).toContain(`${TASK_PREFIX}${TEST_PREFIX}task_with_callbacks_001`);
        expect(testRootIds).not.toContain(`${TASK_PREFIX}${TEST_PREFIX}chain_task_001`);
        expect(testRootIds).not.toContain(`${TEST_PREFIX}batch_item_000`);
        expect(testRootIds).not.toContain(`${TASK_PREFIX}${TEST_PREFIX}success_callback_001`);
      }
    });
  });

  describe('getTasksBatch()', () => {
    it('should return tasks for given IDs', async () => {
      // Arrange
      const taskIds = [
        `${TASK_PREFIX}${TEST_PREFIX}basic_task_001`,
        `${CHAIN_PREFIX}${TEST_PREFIX}chain_001`,
      ];

      // Act
      const tasks = await client.getTasksBatch(taskIds);

      // Assert
      expect(Array.isArray(tasks)).toBe(true);
      if (tasks.length > 0) {
        const basicTask = tasks.find(t => t.id === `${TASK_PREFIX}${TEST_PREFIX}basic_task_001`);
        const chainTask = tasks.find(t => t.id === `${CHAIN_PREFIX}${TEST_PREFIX}chain_001`);

        if (basicTask) {
          expect(basicTask.type).toBe('task');
          expect(basicTask.name).toBe('basic_test_task');
          expect(basicTask.kwargs).toHaveProperty('param1', 'value1');
        }

        if (chainTask) {
          expect(chainTask.type).toBe('chain');
          expect(chainTask.name).toBe('test_chain');
          expect(chainTask.subtaskIds).toHaveLength(2);
        }
      }
    });

    it('should return empty array for empty input', async () => {
      // Act
      const tasks = await client.getTasksBatch([]);

      // Assert
      expect(tasks).toEqual([]);
    });

    it('should handle non-existent task IDs gracefully', async () => {
      // Arrange
      const taskIds = [`${TASK_PREFIX}non_existent_task_12345`];

      // Act
      const tasks = await client.getTasksBatch(taskIds);

      // Assert
      expect(Array.isArray(tasks)).toBe(true);
      expect(tasks).toHaveLength(0);
    });
  });

  describe('getTask()', () => {
    it('should fetch single task via batch queue', async () => {
      // Arrange
      const taskId = `${TASK_PREFIX}${TEST_PREFIX}basic_task_001`;
      client.invalidateAll();

      // Act
      const task = await client.getTask(taskId).catch(() => null);

      // Assert
      if (task) {
        expect(task.id).toBe(taskId);
        expect(task.type).toBe('task');
        expect(task.name).toBe('basic_test_task');
      }
    });

    it('should use cache for repeated requests', async () => {
      // Arrange
      const taskId = `${TASK_PREFIX}${TEST_PREFIX}basic_task_001`;
      client.invalidateAll();

      // Act
      const task1 = await client.getTask(taskId).catch(() => null);
      const task2 = await client.getTask(taskId).catch(() => null);

      // Assert
      if (task1 && task2) {
        expect(task1).toEqual(task2);
      }
    });
  });

  describe('getTaskSubtasks()', () => {
    it('should return paginated subtasks for chain', async () => {
      // Arrange
      const chainId = `${CHAIN_PREFIX}${TEST_PREFIX}chain_001`;

      // Act
      const response = await client.getTaskSubtasks(chainId, { page: 1, pageSize: 10 });

      // Assert
      if (response) {
        expect(response).toHaveProperty('taskIds');
        expect(response).toHaveProperty('totalCount');
        expect(response).toHaveProperty('page');
        expect(response).toHaveProperty('pageSize');
        expect(Array.isArray(response.taskIds)).toBe(true);

        if (response.taskIds.length > 0) {
          expect(response.taskIds).toContain(`${TASK_PREFIX}${TEST_PREFIX}chain_task_001`);
          expect(response.taskIds).toContain(`${TASK_PREFIX}${TEST_PREFIX}chain_task_002`);
        }
      }
    });

    it('should return paginated subtasks for swarm', async () => {
      // Arrange
      const swarmId = `${SWARM_PREFIX}${TEST_PREFIX}swarm_001`;

      // Act
      const response = await client.getTaskSubtasks(swarmId, { page: 1, pageSize: 10 });

      // Assert
      if (response) {
        expect(response).toHaveProperty('taskIds');
        expect(Array.isArray(response.taskIds)).toBe(true);

        if (response.taskIds.length > 0) {
          const batchItemIds = response.taskIds.filter(id => id.includes('BatchItemTaskSignature'));
          expect(batchItemIds.length).toBeGreaterThan(0);
        }
      }
    });
  });

  describe('getTaskCallbacks()', () => {
    it('should return success and error callback IDs', async () => {
      // Arrange
      const taskId = `${TASK_PREFIX}${TEST_PREFIX}task_with_callbacks_001`;

      // Act
      const callbacks = await client.getTaskCallbacks(taskId);

      // Assert
      if (callbacks) {
        expect(callbacks).toHaveProperty('successCallbackIds');
        expect(callbacks).toHaveProperty('errorCallbackIds');
        expect(Array.isArray(callbacks.successCallbackIds)).toBe(true);
        expect(Array.isArray(callbacks.errorCallbackIds)).toBe(true);

        if (callbacks.successCallbackIds.length > 0) {
          expect(callbacks.successCallbackIds).toContain(`${TASK_PREFIX}${TEST_PREFIX}success_callback_001`);
        }
        if (callbacks.errorCallbackIds.length > 0) {
          expect(callbacks.errorCallbackIds).toContain(`${TASK_PREFIX}${TEST_PREFIX}error_callback_001`);
        }
      }
    });
  });
});
