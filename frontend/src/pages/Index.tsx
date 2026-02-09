import { useCallback, useRef } from 'react';
import { TaskGraph, TaskGraphHeader } from '@/components/TaskGraph';

const Index = () => {
  const refetchRef = useRef<(() => Promise<void>) | null>(null);

  const handleRefetchReady = useCallback((refetch: () => Promise<void>) => {
    refetchRef.current = refetch;
  }, []);

  const handleRefresh = useCallback(() => {
    refetchRef.current?.();
  }, []);

  return (
    <div className="flex flex-col h-screen bg-background">
      <TaskGraphHeader onRefresh={handleRefresh} />
      <div className="flex-1">
        <TaskGraph onRefetchReady={handleRefetchReady} />
      </div>
    </div>
  );
};

export default Index;
