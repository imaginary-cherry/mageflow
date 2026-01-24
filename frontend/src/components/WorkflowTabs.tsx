/**
 * WorkflowTabs Component
 *
 * Displays tabs for switching between root workflows.
 */

import React, { memo, useCallback } from 'react';
import { useRootTaskIds, useTask } from '../selectors';
import { useActiveRootId, useIsRootActive } from '../selectors/uiSelectors';
import { useGraphStore } from '../stores/graphStore';
import './WorkflowTabs.css';

// ============================================================================
// Single Tab Component
// ============================================================================

interface TabProps {
  taskId: string;
}

const Tab = memo(function Tab({ taskId }: TabProps) {
  const task = useTask(taskId);
  const isActive = useIsRootActive(taskId);
  const setActiveRoot = useGraphStore((state) => state.actions.setActiveRoot);

  const handleClick = useCallback(() => {
    setActiveRoot(taskId);
  }, [taskId, setActiveRoot]);

  if (!task) {
    return (
      <div className="workflow-tab workflow-tab--loading">
        <div className="workflow-tab__skeleton" />
      </div>
    );
  }

  const tabClassName = [
    'workflow-tab',
    `workflow-tab--${task.status}`,
    isActive && 'workflow-tab--active',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <button className={tabClassName} onClick={handleClick}>
      <span className={`workflow-tab__status status--${task.status}`} />
      <span className="workflow-tab__name" title={task.name}>
        {task.name}
      </span>
      <span className="workflow-tab__type">{task.type}</span>
    </button>
  );
});

// ============================================================================
// WorkflowTabs Component
// ============================================================================

export function WorkflowTabs() {
  const rootTaskIds = useRootTaskIds();

  if (rootTaskIds.length === 0) {
    return (
      <div className="workflow-tabs workflow-tabs--empty">
        <span className="workflow-tabs__empty-text">No workflows found</span>
      </div>
    );
  }

  return (
    <div className="workflow-tabs">
      <div className="workflow-tabs__list">
        {rootTaskIds.map((taskId) => (
          <Tab key={taskId} taskId={taskId} />
        ))}
      </div>
    </div>
  );
}

// ============================================================================
// Default Export
// ============================================================================

export default WorkflowTabs;
