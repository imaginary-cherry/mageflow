import { createContext, useContext, ReactNode } from 'react';
import { TaskClient } from './types';

const TaskClientContext = createContext<TaskClient | null>(null);

interface TaskClientProviderProps {
  client: TaskClient;
  children: ReactNode;
}

export const TaskClientProvider = ({ client, children }: TaskClientProviderProps) => (
  <TaskClientContext.Provider value={client}>
    {children}
  </TaskClientContext.Provider>
);

export const useTaskClient = (): TaskClient => {
  const client = useContext(TaskClientContext);
  if (!client) {
    throw new Error('useTaskClient must be used within a TaskClientProvider');
  }
  return client;
};
