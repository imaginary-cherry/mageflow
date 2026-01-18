import React, { useMemo, useCallback, useEffect } from 'react';
import ReactFlow, {
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  Panel
} from 'reactflow';
import 'reactflow/dist/style.css';

import { TaskNode, ErrorNode } from './CustomNodes';
import { ChainNode } from './ChainNode';
import { SwarmNode } from './SwarmNode';
import { buildChainGraphLayout } from '../utils/chainGraphBuilder';
import { mixedLargeExample } from '../data/largePaginatedTaskData';
import { usePaginationState } from '../hooks/usePaginationState';
import styles from './ChainTaskWorkflow.module.css';

const DEMO_DATA = mixedLargeExample;

const nodeTypes = {
  taskNode: TaskNode,
  errorNode: ErrorNode,
  chainNode: ChainNode,
  swarmNode: SwarmNode
};

const ChainTaskWorkflow = () => {
  const [paginationState, paginationActions] = usePaginationState();

  const { nodes: layoutNodes, edges: layoutEdges } = useMemo(
    () => buildChainGraphLayout(DEMO_DATA, paginationState, paginationActions),
    [paginationState, paginationActions]
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(layoutNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(layoutEdges);

  useEffect(() => {
    setNodes(layoutNodes);
    setEdges(layoutEdges);
  }, [layoutNodes, layoutEdges, setNodes, setEdges]);

  const onConnect = useCallback(
    (params) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  return (
    <div className={styles.container}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        defaultViewport={{ x: 0, y: 0, zoom: 0.8 }}
      >
        <Controls />
        <MiniMap
          nodeColor={(node) => {
            if (node.type === 'chainNode') return '#6366f1';
            if (node.type === 'swarmNode') return '#f59e0b';
            if (node.type === 'errorNode') return '#ef4444';
            return '#4299e1';
          }}
        />
        <Background variant="dots" gap={12} size={1} />
        
        <Panel position="top-left">
          <div className={styles.panel}>
            <h2 className={styles.panelTitle}>Task Workflow</h2>
            <div className={styles.panelContent}>
              <div className={styles.panelSection}>
                Task Types:
              </div>
              <div className={styles.legendItem}>
                <span className={`${styles.legendIcon} ${styles.legendIconChain}`}></span>
                Chain (Sequential)
              </div>
              <div className={styles.legendItem}>
                <span className={`${styles.legendIcon} ${styles.legendIconSwarm}`}></span>
                Swarm (Parallel)
              </div>
              <div className={styles.legendItem}>
                <span className={`${styles.legendIcon} ${styles.legendIconTask}`}></span>
                Normal Task
              </div>
              <hr className={styles.panelDivider} />
              <div className={styles.panelDetails}>
                <strong>Structure:</strong>
                <br />• Chain: tasks run sequentially
                <br />• Swarm: tasks run in parallel
                <br />• Children stay within containers
              </div>
            </div>
          </div>
        </Panel>
      </ReactFlow>
    </div>
  );
};

export default ChainTaskWorkflow;