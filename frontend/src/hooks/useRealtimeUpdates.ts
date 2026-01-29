/**
 * Real-time Updates Hook
 *
 * Connects to WebSocket and updates store on task changes.
 */

import { useEffect, useCallback } from 'react';
import { useGraphStore } from '../stores/graphStore';
import { api } from '../api/client';
import {
  wsClient,
  WSMessage,
  TaskStatusChangedMessage,
  SubtaskAddedMessage,
} from '../api/websocket';

// ============================================================================
// Hook Implementation
// ============================================================================

export function useRealtimeUpdates() {
  const actions = useGraphStore((state) => state.actions);
  const tasks = useGraphStore((state) => state.tasks);

  // Handle task status changes
  const handleStatusChange = useCallback(
    (message: TaskStatusChangedMessage) => {
      // Only update if we have this task loaded
      if (tasks[message.taskId]) {
        actions.updateTaskStatus(message.taskId, message.status);
      }
    },
    [tasks, actions]
  );

  // Handle task updates (refetch task data)
  const handleTaskUpdate = useCallback(
    async (message: WSMessage) => {
      const { taskId } = message;

      // Invalidate cache
      api.invalidateTask(taskId);

      // Refetch if we have this task loaded
      if (tasks[taskId]) {
        try {
          const [updatedTask] = await api.getTasksBatch([taskId]);
          if (updatedTask) {
            actions.setTask(updatedTask);
          }
        } catch (error) {
          console.error(`Failed to refresh task ${taskId}:`, error);
        }
      }
    },
    [tasks, actions]
  );

  // Handle subtask added
  const handleSubtaskAdded = useCallback(
    async (message: SubtaskAddedMessage) => {
      const { taskId, parentId } = message;

      // If parent is loaded, add the new subtask
      const parent = tasks[parentId];
      if (parent) {
        try {
          // Fetch the new subtask
          const [newSubtask] = await api.getTasksBatch([taskId]);
          if (newSubtask) {
            actions.setTask({
              ...newSubtask,
              parentId,
            });

            // Add to parent's subtaskIds
            const currentPage = parent.subtasksPagination.currentPage;
            actions.appendSubtaskIds(parentId, [taskId], currentPage);
          }
        } catch (error) {
          console.error(`Failed to add subtask ${taskId}:`, error);
        }
      }
    },
    [tasks, actions]
  );

  // Handle task removal
  const handleTaskRemoved = useCallback(
    (message: WSMessage) => {
      const { taskId } = message;

      if (tasks[taskId]) {
        actions.removeEdgesForTask(taskId);
        actions.removeTask(taskId);
      }
    },
    [tasks, actions]
  );

  // Subscribe to WebSocket messages
  useEffect(() => {
    // Connect WebSocket
    wsClient.connect();

    // Set up message handlers
    const unsubscribeStatus = wsClient.subscribe(
      'task_status_changed',
      handleStatusChange as (msg: WSMessage) => void
    );

    const unsubscribeUpdate = wsClient.subscribe(
      'task_updated',
      handleTaskUpdate
    );

    const unsubscribeSubtask = wsClient.subscribe(
      'subtask_added',
      handleSubtaskAdded as (msg: WSMessage) => void
    );

    const unsubscribeRemoved = wsClient.subscribe(
      'task_removed',
      handleTaskRemoved
    );

    return () => {
      unsubscribeStatus();
      unsubscribeUpdate();
      unsubscribeSubtask();
      unsubscribeRemoved();
    };
  }, [handleStatusChange, handleTaskUpdate, handleSubtaskAdded, handleTaskRemoved]);

  return {
    isConnected: wsClient.isConnected,
  };
}

// ============================================================================
// Hook for Subscribing to Specific Task
// ============================================================================

export function useTaskSubscription(taskId: string | null) {
  useEffect(() => {
    if (!taskId) return;

    wsClient.subscribeToTask(taskId);

    return () => {
      wsClient.unsubscribeFromTask(taskId);
    };
  }, [taskId]);
}

// ============================================================================
// Hook for Subscribing to Multiple Tasks
// ============================================================================

export function useTasksSubscription(taskIds: string[]) {
  useEffect(() => {
    if (taskIds.length === 0) return;

    taskIds.forEach((id) => wsClient.subscribeToTask(id));

    return () => {
      taskIds.forEach((id) => wsClient.unsubscribeFromTask(id));
    };
  }, [taskIds]);
}
