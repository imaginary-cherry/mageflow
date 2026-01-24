/**
 * SwarmNode Component
 *
 * Displays a swarm (parallel tasks) container with pagination.
 * Children are loaded on-demand when the node is expanded.
 */

import React, { memo, useCallback, useState } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import {
  useTask,
  useSubtaskPagination,
  useVisibleSubtasks,
  useSubtaskIds,
} from '../../selectors';
import { useIsTaskSelected, useIsNodeExpanded } from '../../selectors';
import { useGraphStore } from '../../stores/graphStore';
import { useDimensionCalculator, useProgressiveLoader } from '../../hooks';
import { PaginationControls } from './PaginationControls';
import { TaskNodeCompact } from './TaskNodeCompact';
import './SwarmNode.css';

// ============================================================================
// Types
// ============================================================================

export interface SwarmNodeData {
  taskId: string;
}

// ============================================================================
// SwarmNode Component
// ============================================================================

export const SwarmNode = memo(function SwarmNode({ data }: NodeProps<SwarmNodeData>) {
  const { taskId } = data;

  // Selectors
  const task = useTask(taskId);
  const isSelected = useIsTaskSelected(taskId);
  const isExpanded = useIsNodeExpanded(taskId);
  const pagination = useSubtaskPagination(taskId);
  const visibleSubtasks = useVisibleSubtasks(taskId);
  const subtaskIds = useSubtaskIds(taskId);

  // Hooks
  const { ref } = useDimensionCalculator(taskId);
  const { loadSubtasks } = useProgressiveLoader();

  // Local state for loading
  const [isLoadingPage, setIsLoadingPage] = useState(false);

  // Actions
  const actions = useGraphStore((state) => state.actions);

  // Expand handler
  const handleExpand = useCallback(async () => {
    if (!isExpanded) {
      // Expand and load first page if not loaded
      actions.expandNode(taskId);

      if (task?.subtasksLoadingState === 'idle') {
        setIsLoadingPage(true);
        try {
          await loadSubtasks(taskId, 0);
        } finally {
          setIsLoadingPage(false);
        }
      }
    } else {
      actions.collapseNode(taskId);
    }
  }, [isExpanded, taskId, task?.subtasksLoadingState, actions, loadSubtasks]);

  // Pagination handlers
  const handlePageChange = useCallback(
    async (newPage: number) => {
      if (!pagination) return;

      setIsLoadingPage(true);
      try {
        // Check if page is already loaded
        if (!pagination.loadedPages.has(newPage)) {
          await loadSubtasks(taskId, newPage, pagination.pageSize);
        }
        actions.setSubtaskPage(taskId, newPage);
      } finally {
        setIsLoadingPage(false);
      }
    },
    [taskId, pagination, loadSubtasks, actions]
  );

  // Select handler
  const handleSelect = useCallback(() => {
    actions.selectTask(taskId);
  }, [taskId, actions]);

  if (!task) {
    return (
      <div className="swarm-node swarm-node--loading" ref={ref}>
        <div className="swarm-node__skeleton" />
      </div>
    );
  }

  const nodeClassName = [
    'swarm-node',
    `swarm-node--${task.status}`,
    isSelected && 'swarm-node--selected',
    isExpanded && 'swarm-node--expanded',
  ]
    .filter(Boolean)
    .join(' ');

  const totalPages = pagination
    ? Math.ceil(pagination.totalCount / pagination.pageSize)
    : 0;

  return (
    <div ref={ref} className={nodeClassName}>
      {/* Input handle */}
      <Handle
        type="target"
        position={Position.Left}
        className="swarm-node__handle"
      />

      {/* Header */}
      <div className="swarm-node__header" onClick={handleSelect}>
        <div className="swarm-node__title">
          <span className="swarm-node__type-badge">Swarm</span>
          <span className="swarm-node__name" title={task.name}>
            {task.name}
          </span>
        </div>
        <div className="swarm-node__meta">
          <span className="swarm-node__count">
            {pagination?.totalCount ?? subtaskIds.length} tasks
          </span>
          <button
            className="swarm-node__expand-btn"
            onClick={(e) => {
              e.stopPropagation();
              handleExpand();
            }}
            aria-label={isExpanded ? 'Collapse' : 'Expand'}
          >
            {isExpanded ? '−' : '+'}
          </button>
        </div>
      </div>

      {/* Expanded content with children */}
      {isExpanded && (
        <div className="swarm-node__content">
          {task.subtasksLoadingState === 'loading' || isLoadingPage ? (
            <div className="swarm-node__loading">
              <div className="swarm-node__spinner" />
              Loading tasks...
            </div>
          ) : task.subtasksLoadingState === 'error' ? (
            <div className="swarm-node__error">
              Failed to load tasks
              <button
                className="swarm-node__retry-btn"
                onClick={() => loadSubtasks(taskId, pagination?.currentPage ?? 0)}
              >
                Retry
              </button>
            </div>
          ) : (
            <>
              {/* Subtask list */}
              <div className="swarm-node__children">
                {visibleSubtasks.length === 0 ? (
                  <div className="swarm-node__empty">No tasks</div>
                ) : (
                  visibleSubtasks.map((subtask) => (
                    <TaskNodeCompact
                      key={subtask.id}
                      taskId={subtask.id}
                    />
                  ))
                )}
              </div>

              {/* Pagination */}
              {pagination && totalPages > 1 && (
                <PaginationControls
                  currentPage={pagination.currentPage}
                  totalPages={totalPages}
                  totalCount={pagination.totalCount}
                  pageSize={pagination.pageSize}
                  onPageChange={handlePageChange}
                  isLoading={isLoadingPage}
                />
              )}
            </>
          )}
        </div>
      )}

      {/* Output handle */}
      <Handle
        type="source"
        position={Position.Right}
        className="swarm-node__handle"
      />
    </div>
  );
});

// ============================================================================
// Default Export
// ============================================================================

export default SwarmNode;
