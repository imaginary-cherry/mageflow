import { useState, useEffect, useCallback } from 'react';

export function useTaskData() {
  const [tasks, setTasks] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchTasks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/tasks');
      const data = await response.json();
      if (data.error) throw new Error(data.error);
      setTasks(data.tasks);
    } catch (err) {
      setError(err.message);
      setTasks({});
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchTasks(); }, [fetchTasks]);

  return { tasks, loading, error, refetch: fetchTasks };
}
