/**
 * WorkflowViewer Component
 *
 * Main container component that orchestrates:
 * - Initial data loading
 * - Real-time updates
 * - Layout of tabs, graph, and info panel
 */

import React, { useEffect, useCallback, useState } from 'react';
import { useProgressiveLoader, useRealtimeUpdates } from '../hooks';
import { useIsLoading, useError } from '../selectors/uiSelectors';
import { useGraphStore } from '../stores/graphStore';
import { WorkflowTabs } from './WorkflowTabs';
import { GraphCanvas } from './GraphCanvas';
import { TaskInfoPanel } from './TaskInfoPanel';
import './WorkflowViewer.css';

// ============================================================================
// Error Boundary
// ============================================================================

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends React.Component<
  { children: React.ReactNode; onReset: () => void },
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="workflow-viewer__error">
          <div className="workflow-viewer__error-content">
            <span className="workflow-viewer__error-icon">⚠️</span>
            <h2>Something went wrong</h2>
            <p>{this.state.error?.message || 'An unexpected error occurred'}</p>
            <button
              className="workflow-viewer__error-btn"
              onClick={() => {
                this.setState({ hasError: false, error: null });
                this.props.onReset();
              }}
            >
              Try Again
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

// ============================================================================
// Loading Overlay
// ============================================================================

function LoadingOverlay() {
  return (
    <div className="workflow-viewer__loading">
      <div className="workflow-viewer__spinner" />
      <span>Loading workflows...</span>
    </div>
  );
}

// ============================================================================
// Error Banner
// ============================================================================

interface ErrorBannerProps {
  error: string;
  onDismiss: () => void;
}

function ErrorBanner({ error, onDismiss }: ErrorBannerProps) {
  return (
    <div className="workflow-viewer__error-banner">
      <span className="workflow-viewer__error-text">{error}</span>
      <button
        className="workflow-viewer__error-dismiss"
        onClick={onDismiss}
        aria-label="Dismiss error"
      >
        ×
      </button>
    </div>
  );
}

// ============================================================================
// Toolbar
// ============================================================================

interface ToolbarProps {
  onRefresh: () => void;
  isLoading: boolean;
}

function Toolbar({ onRefresh, isLoading }: ToolbarProps) {
  return (
    <div className="workflow-viewer__toolbar">
      <button
        className="workflow-viewer__toolbar-btn"
        onClick={onRefresh}
        disabled={isLoading}
        title="Refresh workflows"
      >
        {isLoading ? '⟳' : '↻'} Refresh
      </button>
    </div>
  );
}

// ============================================================================
// WorkflowViewer Component
// ============================================================================

export function WorkflowViewer() {
  const [isInitialized, setIsInitialized] = useState(false);
  const { loadRoots, reset } = useProgressiveLoader();
  const { isConnected } = useRealtimeUpdates();

  const isLoading = useIsLoading();
  const error = useError();
  const setError = useGraphStore((state) => state.actions.setError);

  // Initial load
  useEffect(() => {
    const initialize = async () => {
      try {
        await loadRoots();
        setIsInitialized(true);
      } catch (err) {
        console.error('Failed to initialize:', err);
      }
    };

    initialize();
  }, [loadRoots]);

  // Refresh handler
  const handleRefresh = useCallback(async () => {
    reset();
    setIsInitialized(false);
    try {
      await loadRoots();
      setIsInitialized(true);
    } catch (err) {
      console.error('Failed to refresh:', err);
    }
  }, [reset, loadRoots]);

  // Error dismiss
  const handleDismissError = useCallback(() => {
    setError(null);
  }, [setError]);

  return (
    <ErrorBoundary onReset={handleRefresh}>
      <div className="workflow-viewer">
        {/* Header */}
        <header className="workflow-viewer__header">
          <div className="workflow-viewer__header-left">
            <h1 className="workflow-viewer__logo">
              <span className="workflow-viewer__logo-icon">⚡</span>
              MageFlow
            </h1>
            <span
              className={`workflow-viewer__connection ${
                isConnected ? 'workflow-viewer__connection--connected' : ''
              }`}
              title={isConnected ? 'Connected' : 'Disconnected'}
            />
          </div>
          <Toolbar onRefresh={handleRefresh} isLoading={isLoading} />
        </header>

        {/* Error banner */}
        {error && <ErrorBanner error={error} onDismiss={handleDismissError} />}

        {/* Tabs */}
        <WorkflowTabs />

        {/* Main content */}
        <div className="workflow-viewer__main">
          {/* Loading overlay */}
          {!isInitialized && isLoading && <LoadingOverlay />}

          {/* Graph canvas */}
          <div className="workflow-viewer__canvas">
            <GraphCanvas />
          </div>

          {/* Info panel */}
          <TaskInfoPanel />
        </div>
      </div>
    </ErrorBoundary>
  );
}

// ============================================================================
// Default Export
// ============================================================================

export default WorkflowViewer;
