/**
 * GraphCanvas Component
 *
 * Main canvas for displaying the workflow graph using React Flow.
 * Handles layout calculation and node/edge rendering.
 */

import React, { useCallback, useEffect, useMemo } from 'react';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  Node,
  Edge as RFEdge,
  NodeTypes,
  ConnectionMode,
  Panel,
} from 'reactflow';
import 'reactflow/dist/style.css';

import { useGraphStore } from '../stores/graphStore';
import { useActiveRootId } from '../selectors';
import { useAllEdges } from '../selectors/edgeSelectors';
import {
  useLayout,
  layoutToReactFlowNodes,
  edgesToReactFlowEdges,
} from '../layout/layoutEngine';

import { TaskNode, SwarmNode, ChainNode } from './nodes';
import './GraphCanvas.css';

// ============================================================================
// Node Types Registration
// ============================================================================

const nodeTypes: NodeTypes = {
  taskNode: TaskNode,
  swarmNode: SwarmNode,
  chainNode: ChainNode,
};

// ============================================================================
// GraphCanvas Component
// ============================================================================

export function GraphCanvas() {
  const tasks = useGraphStore((state) => state.tasks);
  const activeRootId = useActiveRootId();
  const storeEdges = useAllEdges();
  const setViewport = useGraphStore((state) => state.actions.setViewport);

  // Calculate layout
  const layout = useLayout(activeRootId);

  // Convert to React Flow format
  const rfNodes = useMemo(() => {
    if (!layout) return [];
    return layoutToReactFlowNodes(layout, tasks);
  }, [layout, tasks]);

  const rfEdges = useMemo(() => {
    return edgesToReactFlowEdges(storeEdges);
  }, [storeEdges]);

  // React Flow state
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  // Update nodes when layout changes
  useEffect(() => {
    setNodes(rfNodes as Node[]);
  }, [rfNodes, setNodes]);

  // Update edges when store edges change
  useEffect(() => {
    setEdges(rfEdges as RFEdge[]);
  }, [rfEdges, setEdges]);

  // Handle viewport changes
  const onMoveEnd = useCallback(
    (event: any, viewport: { x: number; y: number; zoom: number }) => {
      setViewport(viewport);
    },
    [setViewport]
  );

  // Fit view on root change
  useEffect(() => {
    // This would trigger a fit view when root changes
    // React Flow handles this internally with fitView prop
  }, [activeRootId]);

  if (!activeRootId) {
    return (
      <div className="graph-canvas graph-canvas--empty">
        <div className="graph-canvas__empty-message">
          <span className="graph-canvas__empty-icon">📊</span>
          <span>Select a workflow to view</span>
        </div>
      </div>
    );
  }

  return (
    <div className="graph-canvas">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onMoveEnd={onMoveEnd}
        nodeTypes={nodeTypes}
        connectionMode={ConnectionMode.Loose}
        fitView
        fitViewOptions={{
          padding: 0.2,
          includeHiddenNodes: false,
        }}
        minZoom={0.1}
        maxZoom={2}
        defaultEdgeOptions={{
          type: 'smoothstep',
          animated: false,
        }}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#333" gap={20} />
        <Controls showInteractive={false} />
        <MiniMap
          nodeColor={(node) => {
            const task = tasks[node.id];
            if (!task) return '#333';

            switch (task.status) {
              case 'active':
                return '#52b788';
              case 'completed':
                return '#40e0d0';
              case 'failed':
                return '#ff6b6b';
              default:
                return '#5a189a';
            }
          }}
          maskColor="rgba(0, 0, 0, 0.8)"
          style={{
            backgroundColor: '#10002b',
          }}
        />

        {/* Graph stats panel */}
        <Panel position="top-right" className="graph-canvas__stats">
          <div className="graph-canvas__stat">
            <span className="graph-canvas__stat-label">Nodes:</span>
            <span className="graph-canvas__stat-value">{nodes.length}</span>
          </div>
          <div className="graph-canvas__stat">
            <span className="graph-canvas__stat-label">Edges:</span>
            <span className="graph-canvas__stat-value">{edges.length}</span>
          </div>
        </Panel>
      </ReactFlow>
    </div>
  );
}

// ============================================================================
// Default Export
// ============================================================================

export default GraphCanvas;
