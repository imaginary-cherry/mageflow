import { useState, useEffect } from 'react';
import { useTaskClient } from '@/services';

interface UseRootTaskIdsResult {
  rootIds: string[];
  loading: boolean;
}

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
