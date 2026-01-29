/**
 * TaskInfoPanel Component
 *
 * Displays detailed information about the selected task.
 */

import React, { memo } from 'react';
import { useSelectedTaskId } from '../selectors/uiSelectors';
import { useTask, useCallbackIds, useSubtaskIds } from '../selectors';
import { useGraphStore } from '../stores/graphStore';
import { Task } from '../types';
import './TaskInfoPanel.css';

// ============================================================================
// Section Components
// ============================================================================

interface SectionProps {
  title: string;
  children: React.ReactNode;
}

const Section = memo(function Section({ title, children }: SectionProps) {
  return (
    <div className="info-panel__section">
      <h3 className="info-panel__section-title">{title}</h3>
      <div className="info-panel__section-content">{children}</div>
    </div>
  );
});

// ============================================================================
// Field Component
// ============================================================================

interface FieldProps {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
}

const Field = memo(function Field({ label, value, mono = false }: FieldProps) {
  return (
    <div className="info-panel__field">
      <span className="info-panel__field-label">{label}</span>
      <span className={`info-panel__field-value ${mono ? 'info-panel__field-value--mono' : ''}`}>
        {value}
      </span>
    </div>
  );
});

// ============================================================================
// Status Badge Component
// ============================================================================

interface StatusBadgeProps {
  status: Task['status'];
}

const StatusBadge = memo(function StatusBadge({ status }: StatusBadgeProps) {
  return <span className={`info-panel__status status--${status}`}>{status}</span>;
});

// ============================================================================
// Task List Component
// ============================================================================

interface TaskListProps {
  taskIds: string[];
  emptyText: string;
}

const TaskList = memo(function TaskList({ taskIds, emptyText }: TaskListProps) {
  const selectTask = useGraphStore((state) => state.actions.selectTask);

  if (taskIds.length === 0) {
    return <span className="info-panel__empty">{emptyText}</span>;
  }

  return (
    <ul className="info-panel__task-list">
      {taskIds.map((id) => (
        <li key={id}>
          <button
            className="info-panel__task-link"
            onClick={() => selectTask(id)}
          >
            {id}
          </button>
        </li>
      ))}
    </ul>
  );
});

// ============================================================================
// Kwargs Display Component
// ============================================================================

interface KwargsDisplayProps {
  kwargs: Record<string, unknown>;
}

const KwargsDisplay = memo(function KwargsDisplay({ kwargs }: KwargsDisplayProps) {
  const entries = Object.entries(kwargs);

  if (entries.length === 0) {
    return <span className="info-panel__empty">No parameters</span>;
  }

  return (
    <div className="info-panel__kwargs">
      {entries.map(([key, value]) => (
        <div key={key} className="info-panel__kwarg">
          <span className="info-panel__kwarg-key">{key}:</span>
          <span className="info-panel__kwarg-value">
            {typeof value === 'object' ? JSON.stringify(value) : String(value)}
          </span>
        </div>
      ))}
    </div>
  );
});

// ============================================================================
// TaskInfoPanel Component
// ============================================================================

export function TaskInfoPanel() {
  const selectedTaskId = useSelectedTaskId();
  const task = useTask(selectedTaskId);
  const callbacks = useCallbackIds(selectedTaskId || '');
  const subtaskIds = useSubtaskIds(selectedTaskId || '');
  const clearSelection = useGraphStore((state) => state.actions.selectTask);

  if (!selectedTaskId || !task) {
    return (
      <div className="info-panel info-panel--empty">
        <div className="info-panel__empty-message">
          <span className="info-panel__empty-icon">👆</span>
          <span>Select a task to view details</span>
        </div>
      </div>
    );
  }

  return (
    <div className="info-panel">
      {/* Header */}
      <div className="info-panel__header">
        <div className="info-panel__title-row">
          <h2 className="info-panel__title">{task.name}</h2>
          <button
            className="info-panel__close-btn"
            onClick={() => clearSelection(null)}
            aria-label="Close panel"
          >
            ×
          </button>
        </div>
        <div className="info-panel__meta">
          <span className={`info-panel__type type--${task.type}`}>{task.type}</span>
          <StatusBadge status={task.status} />
        </div>
      </div>

      {/* Content */}
      <div className="info-panel__content">
        {/* Basic Info */}
        <Section title="Basic Info">
          <Field label="ID" value={task.id} mono />
          <Field label="Type" value={task.type} />
          <Field label="Status" value={<StatusBadge status={task.status} />} />
          <Field label="Created" value={new Date(task.createdAt).toLocaleString()} />
          {task.parentId && <Field label="Parent ID" value={task.parentId} mono />}
        </Section>

        {/* Parameters */}
        <Section title="Parameters">
          <KwargsDisplay kwargs={task.kwargs} />
        </Section>

        {/* Callbacks */}
        <Section title="Success Callbacks">
          <TaskList
            taskIds={callbacks.successCallbackIds}
            emptyText="No success callbacks"
          />
        </Section>

        <Section title="Error Callbacks">
          <TaskList
            taskIds={callbacks.errorCallbackIds}
            emptyText="No error callbacks"
          />
        </Section>

        {/* Subtasks (for containers) */}
        {(task.type === 'swarm' || task.type === 'chain') && (
          <Section title={task.type === 'chain' ? 'Steps' : 'Tasks'}>
            <Field
              label="Total Count"
              value={task.subtasksPagination.totalCount || subtaskIds.length}
            />
            <Field label="Loaded" value={subtaskIds.length} />
            {subtaskIds.length > 0 && (
              <TaskList
                taskIds={subtaskIds.slice(0, 10)}
                emptyText="No subtasks"
              />
            )}
            {subtaskIds.length > 10 && (
              <span className="info-panel__more">
                +{subtaskIds.length - 10} more
              </span>
            )}
          </Section>
        )}

        {/* Dimensions */}
        {task.dimensions && (
          <Section title="Dimensions">
            <Field label="Width" value={`${task.dimensions.width}px`} />
            <Field label="Height" value={`${task.dimensions.height}px`} />
          </Section>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Default Export
// ============================================================================

export default TaskInfoPanel;
