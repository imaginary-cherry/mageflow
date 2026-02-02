import { useCallback, useState, useEffect } from 'react';
import {
  ReactFlow,
  Controls,
  Background,
  BackgroundVariant,
  MiniMap,
  useNodesState,
  useEdgesState,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { Task } from '@/types/task';
import { useTaskGraphLayout } from './useTaskGraphLayout';
import SimpleTaskNode from './SimpleTaskNode';
import ContainerTaskNode from './ContainerTaskNode';
import TaskDetailPanel from './TaskDetailPanel';

const nodeTypes = {
  simpleTask: SimpleTaskNode,
  containerTask: ContainerTaskNode,
};

const TaskGraph = () => {
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);

  const handleTaskClick = useCallback((task: Task) => {
    setSelectedTask(task);
  }, []);

  const { nodes: layoutNodes, edges: layoutEdges } = useTaskGraphLayout({
    onTaskClick: handleTaskClick,
  });

  const [nodes, setNodes, onNodesChange] = useNodesState(layoutNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(layoutEdges);

  // Sync with layout when it changes
  useEffect(() => {
    setNodes(layoutNodes);
    setEdges(layoutEdges);
  }, [layoutNodes, layoutEdges, setNodes, setEdges]);

  return (
    <div className="w-full h-full relative">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        className="bg-background"
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} className="!bg-background" />
        <Controls className="!bg-card !border-border !shadow-lg" />
        <MiniMap 
          className="!bg-card !border-border !shadow-lg"
          nodeColor={(node) => {
            if (node.type === 'simpleTask') return 'hsl(217, 91%, 60%)';
            if (node.type === 'containerTask') {
              const task = (node.data as { task: Task }).task;
              return task.type === 'chain' ? 'hsl(262, 83%, 58%)' : 'hsl(25, 95%, 53%)';
            }
            return 'hsl(var(--muted))';
          }}
        />
      </ReactFlow>

      <TaskDetailPanel 
        task={selectedTask} 
        onClose={() => setSelectedTask(null)} 
      />
    </div>
  );
};

export default TaskGraph;
