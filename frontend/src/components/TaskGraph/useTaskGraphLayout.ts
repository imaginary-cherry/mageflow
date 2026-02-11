import { useMemo } from 'react';
import dagre from 'dagre';
import { Node, Edge } from '@xyflow/react';
import { Task, TaskNodeData } from '@/types/task';
import { 
  SIMPLE_TASK_WIDTH, 
  SIMPLE_TASK_HEIGHT, 
  calculateTaskDimensions 
} from './taskSizeUtils';
import { ContainerNodeData } from './ContainerTaskNode';

// Placeholder size for tasks still loading
const LOADING_NODE_WIDTH = 200;
const LOADING_NODE_HEIGHT = 60;

interface UseTaskGraphLayoutProps {
  onTaskClick?: (task: Task) => void;
  tasks: Record<string, Task>;
  rootTaskIds: string[];
  loadingTasks: Set<string>;
}

export const useTaskGraphLayout = ({ onTaskClick, tasks, rootTaskIds, loadingTasks }: UseTaskGraphLayoutProps) => {
  const { nodes, edges } = useMemo(() => {
    const dagreGraph = new dagre.graphlib.Graph();
    dagreGraph.setDefaultEdgeLabel(() => ({}));
    dagreGraph.setGraph({ rankdir: 'TB', nodesep: 80, ranksep: 100 });

    const nodes: Node<TaskNodeData | ContainerNodeData>[] = [];
    const edges: Edge[] = [];
    const visited = new Set<string>();

    // Get IDs of tasks that are children of containers (should not be rendered as top-level nodes)
    const getNestedChildIds = (task: Task): Set<string> => {
      const nestedIds = new Set<string>();
      if (task.type !== 'simple') {
        task.children_ids.forEach(id => {
          nestedIds.add(id);
          const childTask = tasks[id];
          if (childTask) {
            const childNested = getNestedChildIds(childTask);
            childNested.forEach(nestedId => nestedIds.add(nestedId));
          }
        });
      }
      return nestedIds;
    };

    // Collect all nested child IDs from loaded tasks
    const allNestedChildIds = new Set<string>();
    Object.values(tasks).forEach(task => {
      if (task.type !== 'simple') {
        const nested = getNestedChildIds(task);
        nested.forEach(id => allNestedChildIds.add(id));
      }
    });

    const processTask = (taskId: string, isTopLevel: boolean = true) => {
      if (visited.has(taskId)) return;
      visited.add(taskId);

      const task = tasks[taskId];
      
      if (!task) {
        // Task is still loading — render a placeholder node
        if (loadingTasks.has(taskId)) {
          dagreGraph.setNode(taskId, { width: LOADING_NODE_WIDTH, height: LOADING_NODE_HEIGHT });
          nodes.push({
            id: taskId,
            type: 'loadingTask',
            position: { x: 0, y: 0 },
            data: { taskId } as any,
          });
        }
        return;
      }

      // Skip if this task is a nested child (rendered inside a container)
      if (!isTopLevel && allNestedChildIds.has(taskId)) return;

      const dimensions = calculateTaskDimensions(task, tasks, 1);

      dagreGraph.setNode(taskId, { 
        width: dimensions.width, 
        height: dimensions.height 
      });

      if (task.type === 'simple') {
        nodes.push({
          id: taskId,
          type: 'simpleTask',
          position: { x: 0, y: 0 },
          data: { task, onTaskClick } as TaskNodeData,
        });
      } else {
        nodes.push({
          id: taskId,
          type: 'containerTask',
          position: { x: 0, y: 0 },
          data: { 
            task, 
            onTaskClick,
            width: dimensions.width,
            height: dimensions.height,
          } as ContainerNodeData,
        });
      }

      // Process success callbacks
      task.success_callback_ids.forEach(callbackId => {
        processTask(callbackId, true);
        if (!allNestedChildIds.has(callbackId)) {
          dagreGraph.setEdge(taskId, callbackId);
          edges.push({
            id: `${taskId}-success-${callbackId}`,
            source: taskId,
            target: callbackId,
            type: 'smoothstep',
            style: { stroke: 'hsl(142, 76%, 36%)', strokeWidth: 2 },
            label: 'success',
            labelStyle: { fill: 'hsl(142, 76%, 36%)', fontSize: 10 },
            labelBgStyle: { fill: 'hsl(var(--background))' },
          });
        }
      });

      // Process error callbacks
      task.error_callback_ids.forEach(callbackId => {
        processTask(callbackId, true);
        if (!allNestedChildIds.has(callbackId)) {
          dagreGraph.setEdge(taskId, callbackId);
          edges.push({
            id: `${taskId}-error-${callbackId}`,
            source: taskId,
            target: callbackId,
            type: 'smoothstep',
            style: { stroke: 'hsl(0, 84%, 60%)', strokeWidth: 2 },
            label: 'error',
            labelStyle: { fill: 'hsl(0, 84%, 60%)', fontSize: 10 },
            labelBgStyle: { fill: 'hsl(var(--background))' },
          });
        }
      });
    };

    // Process all root tasks
    rootTaskIds.forEach(id => processTask(id, true));

    // Run dagre layout
    dagre.layout(dagreGraph);

    // Apply positions
    nodes.forEach(node => {
      const nodeWithPosition = dagreGraph.node(node.id);
      if (nodeWithPosition) {
        node.position = {
          x: nodeWithPosition.x - nodeWithPosition.width / 2,
          y: nodeWithPosition.y - nodeWithPosition.height / 2,
        };
      }
    });

    return { nodes, edges };
  }, [onTaskClick, tasks, rootTaskIds, loadingTasks]);

  return { nodes, edges };
};
