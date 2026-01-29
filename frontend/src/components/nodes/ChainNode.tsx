/**
 * ChainNode Component
 *
 * Displays a chain (sequential tasks) container with pagination.
 * Tasks are shown in order with sequence indicators.
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
import './ChainNode.css';

// ============================================================================
// Types
// ============================================================================

export interface ChainNodeData {
  taskId: string;
}

// ============================================================================
// ChainNode Component
// ============================================================================

export const ChainNode = memo(function ChainNode({ data }: NodeProps<ChainNodeData>) {
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
      <div className="chain-node chain-node--loading" ref={ref}>
        <div className="chain-node__skeleton" />
      </div>
    );
  }

  const nodeClassName = [
    'chain-node',
    `chain-node--${task.status}`,
    isSelected && 'chain-node--selected',
    isExpanded && 'chain-node--expanded',
  ]
    .filter(Boolean)
    .join(' ');

  const totalPages = pagination
    ? Math.ceil(pagination.totalCount / pagination.pageSize)
    : 0;

  // Calculate the starting index for the current page
  const startIndex = pagination ? pagination.currentPage * pagination.pageSize : 0;

  return (
    <div ref={ref} className={nodeClassName}>
      {/* Input handle */}
      <Handle
        type="target"
        position={Position.Left}
        className="chain-node__handle"
      />

      {/* Header */}
      <div className="chain-node__header" onClick={handleSelect}>
        <div className="chain-node__title">
          <span className="chain-node__type-badge">Chain</span>
          <span className="chain-node__name" title={task.name}>
            {task.name}
          </span>
        </div>
        <div className="chain-node__meta">
          <span className="chain-node__count">
            {pagination?.totalCount ?? subtaskIds.length} steps
          </span>
          <button
            className="chain-node__expand-btn"
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

      {/* Expanded content with sequential children */}
      {isExpanded && (
        <div className="chain-node__content">
          {task.subtasksLoadingState === 'loading' || isLoadingPage ? (
            <div className="chain-node__loading">
              <div className="chain-node__spinner" />
              Loading steps...
            </div>
          ) : task.subtasksLoadingState === 'error' ? (
            <div className="chain-node__error">
              Failed to load steps
              <button
                className="chain-node__retry-btn"
                onClick={() => loadSubtasks(taskId, pagination?.currentPage ?? 0)}
              >
                Retry
              </button>
            </div>
          ) : (
            <>
              {/* Sequential task list */}
              <div className="chain-node__children">
                {visibleSubtasks.length === 0 ? (
                  <div className="chain-node__empty">No steps</div>
                ) : (
                  visibleSubtasks.map((subtask, index) => (
                    <div key={subtask.id} className="chain-node__step">
                      {/* Step number */}
                      <div className="chain-node__step-number">
                        {startIndex + index + 1}
                      </div>

                      {/* Step connector line */}
                      {index < visibleSubtasks.length - 1 && (
                        <div className="chain-node__step-connector" />
                      )}

                      {/* Task node */}
                      <div className="chain-node__step-task">
                        <TaskNodeCompact taskId={subtask.id} />
                      </div>
                    </div>
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
        className="chain-node__handle"
      />
    </div>
  );
});

// ============================================================================
// Default Export
// ============================================================================

export default ChainNode;
