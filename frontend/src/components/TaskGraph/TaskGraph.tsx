import {useCallback, useEffect, useState} from 'react';
import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
  useEdgesState,
  useNodesState,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import {Task} from '@/types/task';
import {useRootTaskIds, useTasksMap} from '@/hooks/useTaskData';
import {useTaskGraphLayout} from './useTaskGraphLayout';
import SimpleTaskNode from './SimpleTaskNode';
import ContainerTaskNode from './ContainerTaskNode';
import TaskDetailPanel from './TaskDetailPanel';

const nodeTypes = {
  simpleTask: SimpleTaskNode,
  containerTask: ContainerTaskNode,
};

interface TaskGraphProps {
  onRefetchReady?: (refetch: () => Promise<void>) => void;
}

const TaskGraph = ({ onRefetchReady }: TaskGraphProps) => {
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const { tasksMap, loading: tasksLoading, refetch } = useTasksMap();
  const { rootIds, loading: rootIdsLoading } = useRootTaskIds();

  useEffect(() => {
    if (onRefetchReady) {
      onRefetchReady(refetch);
    }
  }, [onRefetchReady, refetch]);

  const handleTaskClick = useCallback((task: Task) => {
    setSelectedTask(task);
  }, []);

  const { nodes: layoutNodes, edges: layoutEdges } = useTaskGraphLayout({
    tasksMap,
    rootTaskIds: rootIds,
    onTaskClick: handleTaskClick,
  });

  const loading = tasksLoading || rootIdsLoading;

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
