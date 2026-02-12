import { TaskGraph, TaskGraphHeader } from '@/components/TaskGraph';
import { TaskStoreProvider, useTaskStore } from '@/stores/TaskStoreContext';

const IndexContent = () => {
  const { refresh } = useTaskStore();

  return (
    <div className="flex flex-col h-screen bg-background">
      <TaskGraphHeader onRefresh={refresh} />
      <div className="flex-1">
        <TaskGraph />
      </div>
    </div>
  );
};

const Index = () => {
  return (
    <TaskStoreProvider>
      <IndexContent />
    </TaskStoreProvider>
  );
};

export default Index;
