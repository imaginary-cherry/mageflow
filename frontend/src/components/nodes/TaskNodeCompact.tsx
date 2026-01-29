/**
 * TaskNodeCompact Component
 *
 * A compact version of TaskNode for display inside container nodes (Swarm/Chain).
 * Shows minimal info but allows clicking to select.
 */

import React, { memo, useCallback } from 'react';
import { useTask } from '../../selectors';
import { useIsTaskSelected } from '../../selectors';
import { useGraphStore } from '../../stores/graphStore';
import { TaskStatus } from '../../types';
import './TaskNodeCompact.css';

// ============================================================================
// Types
// ============================================================================

interface TaskNodeCompactProps {
  taskId: string;
}

// ============================================================================
// Status Dot Component
// ============================================================================

interface StatusDotProps {
  status: TaskStatus;
}

const StatusDot = memo(function StatusDot({ status }: StatusDotProps) {
  const statusColors: Record<TaskStatus, string> = {
    pending: '#9e9e9e',
    active: '#52b788',
    suspended: '#ffd60a',
    interrupted: '#ff9f1c',
    canceled: '#888888',
    completed: '#40e0d0',
    failed: '#ff6b6b',
  };

  return (
    <span
      className={`task-compact__status-dot status-dot--${status}`}
      style={{ backgroundColor: statusColors[status] }}
      title={status}
    />
  );
});

// ============================================================================
// TaskNodeCompact Component
// ============================================================================

export const TaskNodeCompact = memo(function TaskNodeCompact({
  taskId,
}: TaskNodeCompactProps) {
  const task = useTask(taskId);
  const isSelected = useIsTaskSelected(taskId);
  const selectTask = useGraphStore((state) => state.actions.selectTask);

  const handleClick = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      selectTask(taskId);
    },
    [taskId, selectTask]
  );

  if (!task) {
    return (
      <div className="task-compact task-compact--loading">
        <div className="task-compact__skeleton" />
      </div>
    );
  }

  const nodeClassName = [
    'task-compact',
    `task-compact--${task.status}`,
    `task-compact--${task.type}`,
    isSelected && 'task-compact--selected',
  ]
    .filter(Boolean)
    .join(' ');

  // Get type icon
  const typeIcons: Record<string, string> = {
    task: '◆',
    chain: '⟫',
    swarm: '⊞',
    batch_item: '◇',
  };

  return (
    <div className={nodeClassName} onClick={handleClick}>
      <StatusDot status={task.status} />

      <span className="task-compact__type-icon" title={task.type}>
        {typeIcons[task.type] || '◆'}
      </span>

      <span className="task-compact__name" title={task.name}>
        {task.name}
      </span>

      {/* Show nested indicator for container types */}
      {(task.type === 'swarm' || task.type === 'chain') && (
        <span className="task-compact__nested-indicator">
          {task.subtaskIds.length > 0 && `(${task.subtaskIds.length})`}
        </span>
      )}
    </div>
  );
});

// ============================================================================
// Default Export
// ============================================================================

export default TaskNodeCompact;
