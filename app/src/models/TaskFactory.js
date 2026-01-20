import { SimpleTask } from './SimpleTask.js';
import { ChainTask } from './ChainTask.js';
import { SwarmTask } from './SwarmTask.js';
import { extractTypeFromKey } from './TaskModels.js';

export class TaskFactory {
  static transformApiTask(apiTask) {
    const type = extractTypeFromKey(apiTask.key);
    return {
      id: apiTask.key,
      name: apiTask.task_name,
      type: type,
      successCallbacks: apiTask.success_callbacks || [],
      errorCallbacks: apiTask.error_callbacks || [],
      tasks: apiTask.tasks || [],
    };
  }

  /**
   * Create a task instance from data object
   * @param {object} taskData - Task data object with id, name, type, etc.
   * @returns {ChainTask|SwarmTask|SimpleTask} - Task instance of the appropriate subclass
   */
  static createTask(taskData) {
    switch (taskData.type) {
      case 'ChainTaskSignature':
        return new ChainTask(taskData);

      case 'SwarmTaskSignature':
        return new SwarmTask(taskData);

      case 'TaskSignature':
        return new SimpleTask(taskData);

      default:
        throw new Error(`Unknown task type: ${taskData.type}`);
    }
  }

  /**
   * Create multiple task instances from a tasks data object
   * @param {object} tasksData - Object where keys are task IDs and values are task data
   * @returns {Map<string, Task>} - Map of task ID to Task instance
   */
  static createTasksFromData(tasksData) {
    const tasks = new Map();
    
    Object.values(tasksData).forEach(taskData => {
      const task = TaskFactory.createTask(taskData);
      tasks.set(task.id, task);
    });
    
    return tasks;
  }
}