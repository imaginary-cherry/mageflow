/**
 * Layout Engine
 *
 * Calculates node positions using dagre for hierarchical layout.
 * Supports compound nodes (containers with children).
 */

import dagre from 'dagre';
import { Task, Edge, LayoutOptions, DEFAULT_LAYOUT_OPTIONS } from '../types';

// ============================================================================
// Types
// ============================================================================

export interface NodePosition {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface LayoutResult {
  positions: Map<string, NodePosition>;
  graphWidth: number;
  graphHeight: number;
}

// ============================================================================
// Default Dimensions
// ============================================================================

const DEFAULT_NODE_WIDTH = 180;
const DEFAULT_NODE_HEIGHT = 60;
const DEFAULT_CONTAINER_PADDING = 40;

// ============================================================================
// Layout Engine Class
// ============================================================================

export class LayoutEngine {
  private options: LayoutOptions;

  constructor(options: Partial<LayoutOptions> = {}) {
    this.options = { ...DEFAULT_LAYOUT_OPTIONS, ...options };
  }

  /**
   * Calculate layout for a graph starting from a root task
   */
  calculateLayout(
    tasks: Record<string, Task>,
    edges: Edge[],
    rootId: string,
    expandedNodeIds: Set<string>
  ): LayoutResult {
    const g = new dagre.graphlib.Graph({ compound: true });

    // Configure graph
    g.setGraph({
      rankdir: this.options.direction,
      nodesep: this.options.nodeSpacing,
      ranksep: this.options.rankSpacing,
      edgesep: this.options.edgeSpacing,
      marginx: 20,
      marginy: 20,
    });

    g.setDefaultEdgeLabel(() => ({}));

    // Get all relevant task IDs (traverse from root)
    const relevantTaskIds = this.getRelevantTaskIds(tasks, edges, rootId, expandedNodeIds);

    // Add nodes
    for (const taskId of relevantTaskIds) {
      const task = tasks[taskId];
      if (!task) continue;

      const dimensions = this.getNodeDimensions(task, expandedNodeIds);
      g.setNode(taskId, dimensions);

      // Set parent for compound nodes
      if (task.parentId && relevantTaskIds.has(task.parentId) && expandedNodeIds.has(task.parentId)) {
        g.setParent(taskId, task.parentId);
      }
    }

    // Add edges
    for (const edge of edges) {
      if (relevantTaskIds.has(edge.source) && relevantTaskIds.has(edge.target)) {
        // Don't add edges to/from collapsed container contents
        const sourceTask = tasks[edge.source];
        const targetTask = tasks[edge.target];

        if (sourceTask && targetTask) {
          // Skip internal edges of collapsed containers
          if (this.isInternalEdge(edge, tasks, expandedNodeIds)) {
            continue;
          }
          g.setEdge(edge.source, edge.target);
        }
      }
    }

    // Run layout algorithm
    dagre.layout(g);

    // Extract positions
    const positions = new Map<string, NodePosition>();
    let maxX = 0;
    let maxY = 0;

    g.nodes().forEach((nodeId) => {
      const node = g.node(nodeId);
      if (node) {
        positions.set(nodeId, {
          x: node.x - node.width / 2,
          y: node.y - node.height / 2,
          width: node.width,
          height: node.height,
        });
        maxX = Math.max(maxX, node.x + node.width / 2);
        maxY = Math.max(maxY, node.y + node.height / 2);
      }
    });

    return {
      positions,
      graphWidth: maxX + 40,
      graphHeight: maxY + 40,
    };
  }

  /**
   * Get all task IDs that should be included in the layout
   */
  private getRelevantTaskIds(
    tasks: Record<string, Task>,
    edges: Edge[],
    rootId: string,
    expandedNodeIds: Set<string>
  ): Set<string> {
    const ids = new Set<string>();
    const queue = [rootId];

    while (queue.length > 0) {
      const id = queue.shift()!;
      if (ids.has(id)) continue;
      ids.add(id);

      const task = tasks[id];
      if (!task) continue;

      // Add visible subtasks (only if container is expanded)
      if (expandedNodeIds.has(id)) {
        const visibleSubtaskIds = this.getVisibleSubtaskIds(task);
        visibleSubtaskIds.forEach((subId) => queue.push(subId));
      }

      // Add callbacks (always visible)
      task.successCallbackIds.forEach((cbId) => queue.push(cbId));
      task.errorCallbackIds.forEach((cbId) => queue.push(cbId));
    }

    return ids;
  }

  /**
   * Get visible subtask IDs based on pagination
   */
  private getVisibleSubtaskIds(task: Task): string[] {
    const { currentPage, pageSize } = task.subtasksPagination;
    const startIdx = currentPage * pageSize;
    const endIdx = startIdx + pageSize;
    return task.subtaskIds.slice(startIdx, endIdx);
  }

  /**
   * Get dimensions for a node based on its calculated dimensions or defaults
   */
  private getNodeDimensions(
    task: Task,
    expandedNodeIds: Set<string>
  ): { width: number; height: number } {
    // Use calculated dimensions if available
    if (task.dimensions) {
      return {
        width: task.dimensions.width,
        height: task.dimensions.height,
      };
    }

    // Default dimensions based on type and expansion state
    if ((task.type === 'swarm' || task.type === 'chain') && expandedNodeIds.has(task.id)) {
      // Expanded container - larger size
      const visibleCount = Math.min(task.subtasksPagination.pageSize, task.subtaskIds.length);
      return {
        width: DEFAULT_NODE_WIDTH + DEFAULT_CONTAINER_PADDING * 2,
        height: DEFAULT_NODE_HEIGHT + visibleCount * 50 + DEFAULT_CONTAINER_PADDING,
      };
    }

    // Default node size
    return {
      width: DEFAULT_NODE_WIDTH,
      height: DEFAULT_NODE_HEIGHT,
    };
  }

  /**
   * Check if an edge is internal to a collapsed container
   */
  private isInternalEdge(
    edge: Edge,
    tasks: Record<string, Task>,
    expandedNodeIds: Set<string>
  ): boolean {
    const sourceTask = tasks[edge.source];
    const targetTask = tasks[edge.target];

    if (!sourceTask || !targetTask) return false;

    // If both tasks share the same parent and it's collapsed, this is an internal edge
    if (sourceTask.parentId && sourceTask.parentId === targetTask.parentId) {
      if (!expandedNodeIds.has(sourceTask.parentId)) {
        return true;
      }
    }

    return false;
  }

  /**
   * Update options
   */
  setOptions(options: Partial<LayoutOptions>): void {
    this.options = { ...this.options, ...options };
  }
}

// ============================================================================
// Singleton Instance
// ============================================================================

export const layoutEngine = new LayoutEngine();

// ============================================================================
// React Hook
// ============================================================================

import { useMemo } from 'react';
import { useGraphStore } from '../stores/graphStore';

export function useLayout(rootId: string | null): LayoutResult | null {
  const tasks = useGraphStore((state) => state.tasks);
  const edges = useGraphStore((state) => Object.values(state.edges));
  const expandedNodeIds = useGraphStore((state) => state.ui.expandedNodeIds);

  return useMemo(() => {
    if (!rootId) return null;

    return layoutEngine.calculateLayout(tasks, edges, rootId, expandedNodeIds);
  }, [rootId, tasks, edges, expandedNodeIds]);
}

// ============================================================================
// Utility: Convert Layout to React Flow Format
// ============================================================================

export function layoutToReactFlowNodes(
  layoutResult: LayoutResult,
  tasks: Record<string, Task>
): Array<{
  id: string;
  type: string;
  position: { x: number; y: number };
  data: { taskId: string };
  parentNode?: string;
  extent?: 'parent';
}> {
  const nodes: Array<{
    id: string;
    type: string;
    position: { x: number; y: number };
    data: { taskId: string };
    parentNode?: string;
    extent?: 'parent';
  }> = [];

  for (const [taskId, position] of layoutResult.positions) {
    const task = tasks[taskId];
    if (!task) continue;

    const nodeType = getReactFlowNodeType(task.type);

    const node: {
      id: string;
      type: string;
      position: { x: number; y: number };
      data: { taskId: string };
      parentNode?: string;
      extent?: 'parent';
    } = {
      id: taskId,
      type: nodeType,
      position: { x: position.x, y: position.y },
      data: { taskId },
    };

    // Set parent for nested nodes
    if (task.parentId && layoutResult.positions.has(task.parentId)) {
      node.parentNode = task.parentId;
      node.extent = 'parent';
    }

    nodes.push(node);
  }

  return nodes;
}

function getReactFlowNodeType(taskType: Task['type']): string {
  switch (taskType) {
    case 'swarm':
      return 'swarmNode';
    case 'chain':
      return 'chainNode';
    default:
      return 'taskNode';
  }
}

// ============================================================================
// Utility: Convert Edges to React Flow Format
// ============================================================================

export function edgesToReactFlowEdges(
  edges: Edge[]
): Array<{
  id: string;
  source: string;
  target: string;
  type: string;
  animated?: boolean;
  style?: Record<string, string>;
}> {
  return edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    type: 'smoothstep',
    animated: edge.type === 'success',
    style: getEdgeStyle(edge.type),
  }));
}

function getEdgeStyle(type: Edge['type']): Record<string, string> {
  switch (type) {
    case 'success':
      return { stroke: '#40e0d0', strokeWidth: '2' };
    case 'error':
      return { stroke: '#ff6b9d', strokeWidth: '2' };
    case 'subtask':
      return { stroke: '#5a189a', strokeWidth: '1', strokeDasharray: '5,5' };
    case 'sequence':
      return { stroke: '#00bbf9', strokeWidth: '2' };
    default:
      return { stroke: '#5a189a', strokeWidth: '2' };
  }
}
