import { useCallback, useState, useEffect, useRef } from 'react';
import {
  ReactFlow,
  Controls,
  Background,
  BackgroundVariant,
  MiniMap,
  useNodesState,
  useEdgesState,
  type ReactFlowInstance,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { Task } from '@/types/task';
import { useTaskStore } from '@/stores/TaskStoreContext';
import { useTaskGraphLayout } from './useTaskGraphLayout';
import SimpleTaskNode from './SimpleTaskNode';
import ContainerTaskNode from './ContainerTaskNode';
import LoadingTaskNode from './LoadingTaskNode';
import TaskDetailPanel from './TaskDetailPanel';
import { Loader2 } from 'lucide-react';

const nodeTypes = {
  simpleTask: SimpleTaskNode,
  containerTask: ContainerTaskNode,
  loadingTask: LoadingTaskNode,
};

const TaskGraph = () => {
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const { state, loadRootTaskIds } = useTaskStore();

  useEffect(() => {
    loadRootTaskIds();
  }, [loadRootTaskIds]);

  const handleTaskClick = useCallback((task: Task) => {
    setSelectedTask(task);
  }, []);

  const { nodes: layoutNodes, edges: layoutEdges } = useTaskGraphLayout({
    onTaskClick: handleTaskClick,
    tasks: state.tasks,
    rootTaskIds: state.rootTaskIds,
    loadingTasks: state.loadingTasks,
  });

  const [nodes, setNodes, onNodesChange] = useNodesState(layoutNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(layoutEdges);
  const rfInstance = useRef<ReactFlowInstance | null>(null);

  useEffect(() => {
    setNodes(layoutNodes);
    setEdges(layoutEdges);
    // Re-center the graph when layout changes
    if (rfInstance.current && layoutNodes.length > 0) {
      setTimeout(() => rfInstance.current?.fitView({ padding: 0.1 }), 50);
    }
  }, [layoutNodes, layoutEdges, setNodes, setEdges]);

  if (state.rootLoading) {
    return (
      <div className="w-full h-full flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="w-full h-full relative">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onInit={(instance) => { rfInstance.current = instance; }}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.1 }}
        className="bg-background"
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} className="!bg-background" />
        <Controls className="!bg-card !border-border !shadow-lg" />
        <MiniMap 
          className="!bg-card !border-border !shadow-lg"
          nodeColor={(node) => {
            if (node.type === 'loadingTask') return 'hsl(var(--muted))';
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
