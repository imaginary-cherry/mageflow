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
import { usePaginationState } from '../hooks/usePaginationState';
import { useTaskDataLazy } from '../hooks/useTaskDataLazy';
import styles from './TaskWorkflow.module.css';

const nodeTypes = {
  taskNode: TaskNode,
  errorNode: ErrorNode,
  chainNode: ChainNode,
  swarmNode: SwarmNode
};

const TaskWorkflow = () => {
  const {
    tasks,
    taskDepths,
    loading,
    error,
    loadingStates,
    fetchRootTasks,
    loadMoreChildren,
    fetchCallbacks,
    loadMore,
    refetch,
  } = useTaskDataLazy();
  const [paginationState, paginationActions] = usePaginationState();

  useEffect(() => {
    fetchRootTasks();
  }, [fetchRootTasks]);

  const lazyLoadCallbacks = useMemo(() => ({
    onLoadChildren: loadMoreChildren,
    onLoadCallbacks: fetchCallbacks,
    onLoadMore: loadMore,
  }), [loadMoreChildren, fetchCallbacks, loadMore]);

  const { nodes: layoutNodes, edges: layoutEdges } = useMemo(
    () => buildChainGraphLayout(tasks, paginationState, paginationActions, loadingStates, lazyLoadCallbacks, taskDepths),
    [tasks, paginationState, paginationActions, loadingStates, lazyLoadCallbacks, taskDepths]
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

  if (loading) {
    return (
      <div className={styles.container}>
        <div className={styles.loadingContainer}>
          <div className={styles.spinner}></div>
          <p>Loading tasks...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.container}>
        <div className={styles.errorContainer}>
          <p className={styles.errorMessage}>Error: {error}</p>
          <button className={styles.retryButton} onClick={refetch}>Retry</button>
        </div>
      </div>
    );
  }

  if (Object.keys(tasks).length === 0) {
    return (
      <div className={styles.container}>
        <div className={styles.emptyContainer}>
          <p>No tasks found</p>
          <button className={styles.retryButton} onClick={refetch}>Refresh</button>
        </div>
      </div>
    );
  }

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

export default TaskWorkflow;