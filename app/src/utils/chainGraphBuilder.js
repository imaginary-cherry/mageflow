import dagre from '@dagrejs/dagre';
import {TaskFactory} from '../models/TaskFactory.js';
import {ContainerTask} from '../models/ContainerTask.js';

export const buildChainGraphLayout = (tasksData, paginationState = {}, paginationCallbacks = {}) => {
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
  const processedChains = new Set();

  const getPageIndex = (containerId) => paginationState[containerId] ?? 0;

  tasks.forEach(task => {
    if (!task.parent) {
      // Always use page 0 for dimension calculations to ensure consistent container sizes
      const dimensions = task.calculateDimensions(tasks, 0);
      dagreGraph.setNode(task.id, dimensions);
    }
  });

  tasks.forEach(task => {
    if (!task.parent) {
      [...task.successCallbacks, ...task.errorCallbacks].forEach(callbackId => {
        const callbackTask = tasks.get(callbackId);
        if (callbackTask && !callbackTask.parent) {
          dagreGraph.setEdge(task.id, callbackId);
        }
      });
    }
  });

  dagre.layout(dagreGraph);

  const addPaginationToNode = (node, task) => {
    if (!(task instanceof ContainerTask) || !task.needsPagination()) {
      return node;
    }

    const containerId = task.id;
    const currentPage = getPageIndex(containerId);
    const totalPages = task.getTotalPages();

    node.data = {
      ...node.data,
      pagination: {
        currentPage,
        totalPages,
        totalItems: task.tasks.length,
        pageSize: task.pageSize,
      },
      onPrevPage: () => paginationCallbacks.goToPrevPage?.(containerId),
      onNextPage: () => paginationCallbacks.goToNextPage?.(containerId, totalPages),
      onFirstPage: () => paginationCallbacks.goToFirstPage?.(containerId),
      onLastPage: () => paginationCallbacks.goToLastPage?.(containerId, totalPages),
    };

    return node;
  };

  tasks.forEach(task => {
    if (task.parent) return;

    const nodePosition = dagreGraph.node(task.id);

    if (task instanceof ContainerTask && !processedChains.has(task.id)) {
      processedChains.add(task.id);

      const pageIndex = getPageIndex(task.id);
      const containerLayout = task.layoutChildren(tasks, processedChains, pageIndex);

      // Always use page 0 for node dimensions to ensure consistent container sizes
      const containerNode = task.createReactFlowNode(nodePosition, tasks, 0);
      addPaginationToNode(containerNode, task);
      nodes.push(containerNode);

      containerLayout.nodes.forEach(childNode => {
        const childTask = tasks.get(childNode.id);
        if (childTask instanceof ContainerTask) {
          addPaginationToNode(childNode, childTask);
        }
        nodes.push(childNode);
      });

      containerLayout.edges.forEach(edge => {
        edges.push(edge);
      });

    } else if (!task.parent) {
      const taskNode = task.createReactFlowNode(nodePosition, tasks);
      nodes.push(taskNode);
    }
  });
  
  // Create edges between top-level tasks
  tasks.forEach(task => {
    task.successCallbacks.forEach(callbackId => {
      const callbackTask = tasks.get(callbackId);
      if (callbackTask && !callbackTask.parent) {
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
      }
    });

    task.errorCallbacks.forEach(callbackId => {
      const callbackTask = tasks.get(callbackId);
      if (callbackTask && !callbackTask.parent) {
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
      }
    });

  });

  return { nodes, edges };
};