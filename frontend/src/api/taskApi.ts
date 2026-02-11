import { Task } from '@/types/task';
import { mockTasks, rootTaskIds } from '@/data/mockTasks';

const DELAY_MIN = 400;
const DELAY_MAX = 1200;

const randomDelay = () =>
  new Promise<void>(resolve =>
    setTimeout(resolve, DELAY_MIN + Math.random() * (DELAY_MAX - DELAY_MIN))
  );

export const fetchRootTaskIds = async (): Promise<string[]> => {
  await randomDelay();
  return [...rootTaskIds];
};

export const fetchTask = async (id: string): Promise<Task | null> => {
  await randomDelay();
  const task = mockTasks[id];
  return task ? { ...task } : null;
};
