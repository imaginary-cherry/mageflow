/**
 * Edge Selectors
 *
 * Memoized selectors for edge data.
 */

import { useMemo } from 'react';
import { shallow } from 'zustand/shallow';
import { useGraphStore } from '../stores/graphStore';
import { Edge, EdgeType } from '../types';

// ============================================================================
// Single Edge Selectors
// ============================================================================

/**
 * Get a single edge by ID
 */
export function useEdge(edgeId: string): Edge | null {
  return useGraphStore((state) => state.edges[edgeId] ?? null);
}

// ============================================================================
// Filtered Edge Selectors
// ============================================================================

/**
 * Get all edges
 */
export function useAllEdges(): Edge[] {
  return useGraphStore((state) => Object.values(state.edges), shallow);
}

/**
 * Get all edge IDs
 */
export function useAllEdgeIds(): string[] {
  return useGraphStore((state) => Object.keys(state.edges), shallow);
}

/**
 * Get edge count
 */
export function useEdgeCount(): number {
  return useGraphStore((state) => Object.keys(state.edges).length);
}

/**
 * Get edges by type
 */
export function useEdgesByType(type: EdgeType): Edge[] {
  return useGraphStore(
    (state) =>
      Object.values(state.edges).filter((edge) => edge.type === type),
    shallow
  );
}

// ============================================================================
// Task-Specific Edge Selectors
// ============================================================================

/**
 * Get edges where task is the source
 */
export function useOutgoingEdges(taskId: string): Edge[] {
  return useGraphStore(
    (state) =>
      Object.values(state.edges).filter((edge) => edge.source === taskId),
    shallow
  );
}

/**
 * Get edges where task is the target
 */
export function useIncomingEdges(taskId: string): Edge[] {
  return useGraphStore(
    (state) =>
      Object.values(state.edges).filter((edge) => edge.target === taskId),
    shallow
  );
}

/**
 * Get all edges connected to a task (incoming + outgoing)
 */
export function useTaskEdges(taskId: string): Edge[] {
  return useGraphStore(
    (state) =>
      Object.values(state.edges).filter(
        (edge) => edge.source === taskId || edge.target === taskId
      ),
    shallow
  );
}

/**
 * Get success callback edges for a task
 */
export function useSuccessEdges(taskId: string): Edge[] {
  return useGraphStore(
    (state) =>
      Object.values(state.edges).filter(
        (edge) => edge.source === taskId && edge.type === 'success'
      ),
    shallow
  );
}

/**
 * Get error callback edges for a task
 */
export function useErrorEdges(taskId: string): Edge[] {
  return useGraphStore(
    (state) =>
      Object.values(state.edges).filter(
        (edge) => edge.source === taskId && edge.type === 'error'
      ),
    shallow
  );
}

/**
 * Get subtask edges (parent -> child)
 */
export function useSubtaskEdges(parentId: string): Edge[] {
  return useGraphStore(
    (state) =>
      Object.values(state.edges).filter(
        (edge) => edge.source === parentId && edge.type === 'subtask'
      ),
    shallow
  );
}

// ============================================================================
// Graph-Wide Edge Selectors
// ============================================================================

/**
 * Get edges for a specific root graph
 * Only returns edges where both source and target are descendants of root
 */
export function useEdgesForRoot(rootId: string): Edge[] {
  const tasks = useGraphStore((state) => state.tasks);
  const edges = useGraphStore((state) => state.edges);

  return useMemo(() => {
    // Get all descendant IDs including the root
    const relevantIds = new Set<string>([rootId]);
    const queue = [rootId];

    while (queue.length > 0) {
      const currentId = queue.shift()!;
      const task = tasks[currentId];
      if (!task) continue;

      // Add subtasks
      for (const subtaskId of task.subtaskIds) {
        if (!relevantIds.has(subtaskId)) {
          relevantIds.add(subtaskId);
          queue.push(subtaskId);
        }
      }

      // Add callbacks
      for (const callbackId of [...task.successCallbackIds, ...task.errorCallbackIds]) {
        if (!relevantIds.has(callbackId)) {
          relevantIds.add(callbackId);
          queue.push(callbackId);
        }
      }
    }

    // Filter edges to only those within the graph
    return Object.values(edges).filter(
      (edge) => relevantIds.has(edge.source) && relevantIds.has(edge.target)
    );
  }, [rootId, tasks, edges]);
}

// ============================================================================
// Edge Existence Checks
// ============================================================================

/**
 * Check if edge exists between two tasks
 */
export function useEdgeExists(sourceId: string, targetId: string): boolean {
  return useGraphStore((state) =>
    Object.values(state.edges).some(
      (edge) => edge.source === sourceId && edge.target === targetId
    )
  );
}

/**
 * Check if edge exists by ID
 */
export function useEdgeExistsById(edgeId: string): boolean {
  return useGraphStore((state) => edgeId in state.edges);
}
