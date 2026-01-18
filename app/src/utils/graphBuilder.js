import dagre from '@dagrejs/dagre';
import { TaskFactory } from '../models/TaskFactory.js';

export const buildGraphLayout = (tasksData) => {
  // Convert data to task objects
  const tasks = TaskFactory.createTasksFromData(tasksData);
  const dagreGraph = new dagre.graphlib.Graph();
  
  dagreGraph.setGraph({
    rankdir: 'LR',
    align: 'UL',
    nodesep: 30,
    ranksep: 80,
    marginx: 20,
    marginy: 20,
    ranker: 'longest-path'
  });
  
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  
  const nodes = [];
  const edges = [];
  
  // Set nodes in Dagre
  tasks.forEach(task => {
    const dimensions = task.calculateDimensions(tasks);
    dagreGraph.setNode(task.id, dimensions);
  });
  
  // Set edges and create edge objects
  tasks.forEach(task => {
    task.successCallbacks.forEach(callbackId => {
      dagreGraph.setEdge(task.id, callbackId);
      edges.push({
        id: `${task.id}-success-${callbackId}`,
        source: task.id,
        target: callbackId,
        type: 'smoothstep',
        animated: true,
        style: { stroke: '#10b981', strokeWidth: 2 },
        label: 'success',
        labelStyle: { fill: '#10b981', fontWeight: 600, fontSize: 12 },
        labelBgStyle: { fill: 'white' },
        sourceHandle: 'success',
        targetHandle: null
      });
    });
    
    task.errorCallbacks.forEach(callbackId => {
      dagreGraph.setEdge(task.id, callbackId);
      edges.push({
        id: `${task.id}-error-${callbackId}`,
        source: task.id,
        target: callbackId,
        type: 'smoothstep',
        animated: false,
        style: { stroke: '#ef4444', strokeWidth: 2, strokeDasharray: '5,5' },
        label: 'error',
        labelStyle: { fill: '#ef4444', fontWeight: 600, fontSize: 12 },
        labelBgStyle: { fill: 'white' },
        sourceHandle: 'error',
        targetHandle: null
      });
    });
  });
  
  dagre.layout(dagreGraph);
  
  // Create React Flow nodes using task objects
  tasks.forEach(task => {
    const nodePosition = dagreGraph.node(task.id);
    const taskNode = task.createReactFlowNode(nodePosition, tasks);
    nodes.push(taskNode);
  });
  
  return { nodes, edges };
};