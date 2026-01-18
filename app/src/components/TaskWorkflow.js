import React, { useMemo, useCallback } from 'react';
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
import { buildGraphLayout } from '../utils/graphBuilder';
import { sampleTasks } from '../data/taskData';

const nodeTypes = {
  taskNode: TaskNode,
  errorNode: ErrorNode
};

const TaskWorkflow = () => {
  const { nodes: initialNodes, edges: initialEdges } = useMemo(
    () => buildGraphLayout(sampleTasks),
    []
  );

  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  const onConnect = useCallback(
    (params) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  return (
    <div style={{ width: '100vw', height: '100vh' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
      >
        <Controls />
        <MiniMap 
          nodeColor={() => '#4299e1'}
        />
        <Background variant="dots" gap={12} size={1} />
        
        <Panel position="top-left">
          <div style={{
            background: 'white',
            padding: '15px',
            borderRadius: '8px',
            boxShadow: '0 4px 6px rgba(0,0,0,0.1)'
          }}>
            <h2 style={{ margin: '0 0 10px 0', fontSize: '18px' }}>Task Workflow Manager</h2>
            <div style={{ fontSize: '12px', lineHeight: '1.6' }}>
              <div style={{ marginBottom: '10px', fontWeight: '600' }}>
                Connection Types:
              </div>
              <div style={{ marginBottom: '5px', color: '#10b981' }}>
                → Solid Green Line: Success Callback
              </div>
              <div style={{ color: '#ef4444' }}>
                ⇢ Dashed Red Line: Error Callback
              </div>
            </div>
          </div>
        </Panel>
      </ReactFlow>
    </div>
  );
};

export default TaskWorkflow;