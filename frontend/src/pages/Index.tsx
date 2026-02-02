import { TaskGraph, TaskGraphHeader } from '@/components/TaskGraph';

const Index = () => {
  const handleRefresh = () => {
    console.log('Refreshing tasks...');
    // Will be connected to API later
  };

  return (
    <div className="flex flex-col h-screen bg-background">
      <TaskGraphHeader onRefresh={handleRefresh} />
      <div className="flex-1">
        <TaskGraph />
      </div>
    </div>
  );
};

export default Index;
