import { useState, useEffect, useCallback } from 'react';
import { Task } from '@/types/task';
import { useTaskClient } from '@/services';

interface UseTasksMapResult {
  tasksMap: Record<string, Task>;
  loading: boolean;
  refetch: () => Promise<void>;
}

interface UseRootTaskIdsResult {
  rootIds: string[];
  loading: boolean;
}

export const useTasksMap = (): UseTasksMapResult => {
  const client = useTaskClient();
  const [tasksMap, setTasksMap] = useState<Record<string, Task>>({});
  const [loading, setLoading] = useState(true);

  const refetch = useCallback(async () => {
    setLoading(true);
    const data = await client.getTasksMap();
    setTasksMap(data);
    setLoading(false);
  }, [client]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { tasksMap, loading, refetch };
};

export const useRootTaskIds = (): UseRootTaskIdsResult => {
  const client = useTaskClient();
  const [rootIds, setRootIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetch = async () => {
      const ids = await client.getRootTaskIds();
      setRootIds(ids);
      setLoading(false);
    };
    fetch();
  }, [client]);

  return { rootIds, loading };
};
