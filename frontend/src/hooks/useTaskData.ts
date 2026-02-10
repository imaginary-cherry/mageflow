import { useState, useEffect } from 'react';
import { useTaskClient } from '@/services';

interface UseRootTaskIdsResult {
  rootIds: string[];
  loading: boolean;
  error: string | null;
}

export const useRootTaskIds = (): UseRootTaskIdsResult => {
  const client = useTaskClient();
  const [rootIds, setRootIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchRoots = async () => {
      try {
        const ids = await client.getRootTaskIds();
        setRootIds(ids);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to fetch root tasks';
        console.error('useRootTaskIds error:', err);
        setError(message);
      } finally {
        setLoading(false);
      }
    };
    fetchRoots();
  }, [client]);

  return { rootIds, loading, error };
};
