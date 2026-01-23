/**
 * UI State Selectors
 *
 * Selectors for UI-related state.
 */

import { shallow } from 'zustand/shallow';
import { useGraphStore } from '../stores/graphStore';
import { Viewport } from '../types';

// ============================================================================
// Selection Selectors
// ============================================================================

/**
 * Get currently selected task ID
 */
export function useSelectedTaskId(): string | null {
  return useGraphStore((state) => state.ui.selectedTaskId);
}

/**
 * Check if a specific task is selected
 */
export function useIsTaskSelected(taskId: string): boolean {
  return useGraphStore((state) => state.ui.selectedTaskId === taskId);
}

// ============================================================================
// Expansion Selectors
// ============================================================================

/**
 * Get all expanded node IDs
 */
export function useExpandedNodeIds(): Set<string> {
  return useGraphStore((state) => state.ui.expandedNodeIds);
}

/**
 * Check if a specific node is expanded
 */
export function useIsNodeExpanded(taskId: string): boolean {
  return useGraphStore((state) => state.ui.expandedNodeIds.has(taskId));
}

/**
 * Get count of expanded nodes
 */
export function useExpandedNodeCount(): number {
  return useGraphStore((state) => state.ui.expandedNodeIds.size);
}

// ============================================================================
// Active Root Selectors
// ============================================================================

/**
 * Get active root task ID
 */
export function useActiveRootId(): string | null {
  return useGraphStore((state) => state.ui.activeRootId);
}

/**
 * Check if a specific root is active
 */
export function useIsRootActive(taskId: string): boolean {
  return useGraphStore((state) => state.ui.activeRootId === taskId);
}

// ============================================================================
// Viewport Selectors
// ============================================================================

/**
 * Get current viewport
 */
export function useViewport(): Viewport {
  return useGraphStore((state) => state.ui.viewport, shallow);
}

/**
 * Get viewport zoom level
 */
export function useZoomLevel(): number {
  return useGraphStore((state) => state.ui.viewport.zoom);
}

/**
 * Get viewport position
 */
export function useViewportPosition(): { x: number; y: number } {
  return useGraphStore(
    (state) => ({ x: state.ui.viewport.x, y: state.ui.viewport.y }),
    shallow
  );
}

// ============================================================================
// Loading/Error Selectors
// ============================================================================

/**
 * Get global loading state
 */
export function useIsLoading(): boolean {
  return useGraphStore((state) => state.ui.isLoading);
}

/**
 * Get global error
 */
export function useError(): string | null {
  return useGraphStore((state) => state.ui.error);
}

/**
 * Check if there's an error
 */
export function useHasError(): boolean {
  return useGraphStore((state) => state.ui.error !== null);
}

// ============================================================================
// Combined UI State
// ============================================================================

/**
 * Get full UI state (for components that need multiple values)
 */
export function useUIState() {
  return useGraphStore((state) => state.ui, shallow);
}
