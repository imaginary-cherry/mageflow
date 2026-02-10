import { useState, useEffect, useCallback } from 'react';
import { useQuery, useQueries } from '@tanstack/react-query';
import { Task } from '@/types/task';
import { useTaskClient } from '@/services';

const PAGE_SIZE = 50;
const STALE_TIME = 30_000;

export interface TaskTreeNode {
  task: Task;
  childrenPage: number;
  totalChildren: number;
  totalChildrenPages: number;
  loading: boolean;
  error: Error | null;
}

export interface UseTaskTreeResult {
  tasksMap: Record<string, Task>;
  nodeStates: Record<string, TaskTreeNode>;
  loading: boolean;
  loadChildrenPage: (taskId: string, page: number) => void;
}

export function useTaskTree(rootIds: string[]): UseTaskTreeResult {
  const client = useTaskClient();
  const [tasksMap, setTasksMap] = useState<Record<string, Task>>({});
  const [nodeStates, setNodeStates] = useState<Record<string, TaskTreeNode>>({});
  const [tasksToExpand, setTasksToExpand] = useState<Set<string>>(new Set());
  const [visitedIds, setVisitedIds] = useState<Set<string>>(new Set());
  const [pageRequests, setPageRequests] = useState<Record<string, number>>({});

  const rootTasksQuery = useQuery({
    queryKey: ['tasks', 'batch', rootIds],
    queryFn: async () => {
      if (rootIds.length === 0) return [];
      return client.getTasksBatch(rootIds);
    },
    enabled: rootIds.length > 0,
    staleTime: STALE_TIME,
  });

  useEffect(() => {
    if (rootTasksQuery.data) {
      const newTasksMap: Record<string, Task> = {};
      const newNodeStates: Record<string, TaskTreeNode> = {};
      const toExpand = new Set<string>();

      for (const task of rootTasksQuery.data) {
        newTasksMap[task.id] = task;
        newNodeStates[task.id] = {
          task,
          childrenPage: 1,
          totalChildren: 0,
          totalChildrenPages: 0,
          loading: false,
          error: null,
        };

        if (task.children_ids.length > 0 || task.success_callback_ids.length > 0 || task.error_callback_ids.length > 0) {
          toExpand.add(task.id);
        }
      }

      setTasksMap(prev => ({ ...prev, ...newTasksMap }));
      setNodeStates(prev => ({ ...prev, ...newNodeStates }));
      setTasksToExpand(toExpand);
      setVisitedIds(new Set(rootIds));
    }
  }, [rootTasksQuery.data, rootIds]);

  const expansionQueries = useQueries({
    queries: Array.from(tasksToExpand).map(taskId => {
      const task = tasksMap[taskId];
      const requestedPage = pageRequests[taskId] || 1;
      const hasChildren = task && task.children_ids.length > 0;

      return {
        queryKey: ['task', taskId, 'expand', requestedPage],
        queryFn: async () => {
          const hasCallbacks = task.success_callback_ids.length > 0 || task.error_callback_ids.length > 0;

          const results: {
            childrenTasks: Task[];
            callbackTasks: Task[];
            totalChildren: number;
            totalPages: number;
          } = {
            childrenTasks: [],
            callbackTasks: [],
            totalChildren: 0,
            totalPages: 0,
          };

          if (hasChildren) {
            const childrenData = await client.getChildren(taskId, requestedPage, PAGE_SIZE);
            results.childrenTasks = childrenData.tasks;
            results.totalChildren = childrenData.total;
            results.totalPages = childrenData.total_pages;
          }

          if (hasCallbacks) {
            const callbackIds = [
              ...task.success_callback_ids,
              ...task.error_callback_ids,
            ];
            const callbackTasks = await client.getTasksBatch(callbackIds);
            results.callbackTasks = callbackTasks;
          }

          return results;
        },
        enabled: !!task && !visitedIds.has(taskId),
        staleTime: STALE_TIME,
        retry: 1,
      };
    }),
  });

  useEffect(() => {
    const newTasksMap: Record<string, Task> = {};
    const newNodeStates: Record<string, TaskTreeNode> = {};
    const newToExpand = new Set<string>();
    const newVisited = new Set(visitedIds);

    expansionQueries.forEach((query, index) => {
      const taskId = Array.from(tasksToExpand)[index];
      if (!taskId) return;

      const task = tasksMap[taskId];
      if (!task) return;

      if (query.data) {
        const { childrenTasks, callbackTasks, totalChildren, totalPages } = query.data;
        const allNewTasks = [...childrenTasks, ...callbackTasks];

        for (const newTask of allNewTasks) {
          newTasksMap[newTask.id] = newTask;

          if (!nodeStates[newTask.id]) {
            newNodeStates[newTask.id] = {
              task: newTask,
              childrenPage: 1,
              totalChildren: 0,
              totalChildrenPages: 0,
              loading: false,
              error: null,
            };
          }

          if (
            (newTask.children_ids.length > 0 ||
              newTask.success_callback_ids.length > 0 ||
              newTask.error_callback_ids.length > 0) &&
            !newVisited.has(newTask.id)
          ) {
            newToExpand.add(newTask.id);
          }
        }

        newNodeStates[taskId] = {
          task,
          childrenPage: pageRequests[taskId] || 1,
          totalChildren,
          totalChildrenPages: totalPages,
          loading: false,
          error: null,
        };

        newVisited.add(taskId);
      } else if (query.error) {
        newNodeStates[taskId] = {
          task,
          childrenPage: pageRequests[taskId] || 1,
          totalChildren: 0,
          totalChildrenPages: 0,
          loading: false,
          error: query.error instanceof Error ? query.error : new Error(String(query.error)),
        };
        newVisited.add(taskId);
      } else if (query.isLoading) {
        newNodeStates[taskId] = {
          task,
          childrenPage: pageRequests[taskId] || 1,
          totalChildren: nodeStates[taskId]?.totalChildren || 0,
          totalChildrenPages: nodeStates[taskId]?.totalChildrenPages || 0,
          loading: true,
          error: null,
        };
      }
    });

    if (Object.keys(newTasksMap).length > 0) {
      setTasksMap(prev => ({ ...prev, ...newTasksMap }));
    }

    if (Object.keys(newNodeStates).length > 0) {
      setNodeStates(prev => ({ ...prev, ...newNodeStates }));
    }

    if (newToExpand.size > 0) {
      setTasksToExpand(prev => new Set([...prev, ...newToExpand]));
    }

    if (newVisited.size > visitedIds.size) {
      setVisitedIds(newVisited);
    }
  }, [expansionQueries, tasksToExpand, tasksMap, nodeStates, visitedIds, pageRequests]);

  const loadChildrenPage = useCallback((taskId: string, page: number) => {
    setPageRequests(prev => ({ ...prev, [taskId]: page }));
    setVisitedIds(prev => {
      const newVisited = new Set(prev);
      newVisited.delete(taskId);
      return newVisited;
    });
    setTasksToExpand(prev => new Set([...prev, taskId]));
  }, []);

  const loading = rootTasksQuery.isLoading || expansionQueries.some(q => q.isLoading);

  return {
    tasksMap,
    nodeStates,
    loading,
    loadChildrenPage,
  };
}
