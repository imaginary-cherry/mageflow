/**
 * Edge Types for MageFlow Graph Visualization
 */

export type EdgeType = 'success' | 'error' | 'subtask' | 'sequence';

export interface Edge {
  id: string;
  source: string;
  target: string;
  type: EdgeType;
  label?: string;
}

export function createEdgeId(source: string, target: string, type: EdgeType): string {
  return `${source}->${target}:${type}`;
}

export function createSuccessEdge(source: string, target: string): Edge {
  return {
    id: createEdgeId(source, target, 'success'),
    source,
    target,
    type: 'success',
  };
}

export function createErrorEdge(source: string, target: string): Edge {
  return {
    id: createEdgeId(source, target, 'error'),
    source,
    target,
    type: 'error',
  };
}

export function createSubtaskEdge(parent: string, child: string): Edge {
  return {
    id: createEdgeId(parent, child, 'subtask'),
    source: parent,
    target: child,
    type: 'subtask',
  };
}

export function createSequenceEdge(from: string, to: string): Edge {
  return {
    id: createEdgeId(from, to, 'sequence'),
    source: from,
    target: to,
    type: 'sequence',
  };
}
