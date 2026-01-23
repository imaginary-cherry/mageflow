/**
 * TaskNode Component
 *
 * Displays a single task node in the graph.
 * Memoized to only re-render when its specific data changes.
 */

import React, { memo, useCallback } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { useTask, useTaskStatus } from '../../selectors';
import { useIsTaskSelected, useIsNodeExpanded } from '../../selectors';
import { useGraphStore } from '../../stores/graphStore';
import { useDimensionCalculator } from '../../hooks';
import { TaskStatus } from '../../types';
import './TaskNode.css';

// ============================================================================
// Types
// ============================================================================

export interface TaskNodeData {
  taskId: string;
}

// ============================================================================
// Status Badge Component
// ============================================================================

interface StatusBadgeProps {
  status: TaskStatus;
}

const StatusBadge = memo(function StatusBadge({ status }: StatusBadgeProps) {
  const statusConfig: Record<TaskStatus, { label: string; className: string }> = {
    pending: { label: 'Pending', className: 'status--pending' },
    active: { label: 'Active', className: 'status--active' },
    suspended: { label: 'Suspended', className: 'status--suspended' },
    interrupted: { label: 'Interrupted', className: 'status--interrupted' },
    canceled: { label: 'Canceled', className: 'status--canceled' },
    completed: { label: 'Completed', className: 'status--completed' },
    failed: { label: 'Failed', className: 'status--failed' },
  };

  const config = statusConfig[status];

  return (
    <span className={`task-node__status ${config.className}`}>
      {config.label}
    </span>
  );
});

// ============================================================================
// Type Badge Component
// ============================================================================

interface TypeBadgeProps {
  type: string;
}

const TypeBadge = memo(function TypeBadge({ type }: TypeBadgeProps) {
  const typeConfig: Record<string, { label: string; className: string }> = {
    task: { label: 'Task', className: 'type--task' },
    chain: { label: 'Chain', className: 'type--chain' },
    swarm: { label: 'Swarm', className: 'type--swarm' },
    batch_item: { label: 'Batch', className: 'type--batch' },
  };

  const config = typeConfig[type] || { label: type, className: 'type--unknown' };

  return (
    <span className={`task-node__type ${config.className}`}>
      {config.label}
    </span>
  );
});

// ============================================================================
// TaskNode Component
// ============================================================================

export const TaskNode = memo(function TaskNode({ data }: NodeProps<TaskNodeData>) {
  const { taskId } = data;

  // Selectors - each only re-renders when its specific data changes
  const task = useTask(taskId);
  const isSelected = useIsTaskSelected(taskId);

  // Dimension calculator
  const { ref } = useDimensionCalculator(taskId);

  // Actions
  const selectTask = useGraphStore((state) => state.actions.selectTask);

  // Handlers
  const handleClick = useCallback(() => {
    selectTask(taskId);
  }, [taskId, selectTask]);

  if (!task) {
    return (
      <div className="task-node task-node--loading" ref={ref}>
        <div className="task-node__skeleton" />
      </div>
    );
  }

  const nodeClassName = [
    'task-node',
    `task-node--${task.status}`,
    `task-node--${task.type}`,
    isSelected && 'task-node--selected',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div
      ref={ref}
      className={nodeClassName}
      onClick={handleClick}
    >
      {/* Input handle */}
      <Handle
        type="target"
        position={Position.Left}
        className="task-node__handle task-node__handle--input"
      />

      {/* Header */}
      <div className="task-node__header">
        <TypeBadge type={task.type} />
        <StatusBadge status={task.status} />
      </div>

      {/* Content */}
      <div className="task-node__content">
        <div className="task-node__name" title={task.name}>
          {task.name}
        </div>
      </div>

      {/* Output handle */}
      <Handle
        type="source"
        position={Position.Right}
        className="task-node__handle task-node__handle--output"
      />
    </div>
  );
});

// ============================================================================
// Default Export
// ============================================================================

export default TaskNode;
