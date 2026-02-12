import React, {createContext, useCallback, useContext, useReducer, useRef} from 'react';
import {Task} from '@/types/task';
import {useTaskClient} from "@/services";

interface TaskStoreState {
  tasks: Record<string, Task>;
  loadingTasks: Set<string>;
  rootTaskIds: string[];
  rootLoading: boolean;
}

type Action =
  | { type: 'SET_ROOT_IDS'; ids: string[] }
  | { type: 'SET_ROOT_LOADING'; loading: boolean }
  | { type: 'SET_TASK'; task: Task }
  | { type: 'SET_LOADING'; id: string }
  | { type: 'CLEAR_LOADING'; id: string }
  | { type: 'CLEAR_ALL' };

const initialState: TaskStoreState = {
  tasks: {},
  loadingTasks: new Set(),
  rootTaskIds: [],
  rootLoading: false,
};

function reducer(state: TaskStoreState, action: Action): TaskStoreState {
  switch (action.type) {
    case 'SET_ROOT_IDS':
      return { ...state, rootTaskIds: action.ids, rootLoading: false };
    case 'SET_ROOT_LOADING':
      return { ...state, rootLoading: action.loading };
    case 'SET_TASK': {
      const newTasks = { ...state.tasks, [action.task.id]: action.task };
      const newLoading = new Set(state.loadingTasks);
      newLoading.delete(action.task.id);
      return { ...state, tasks: newTasks, loadingTasks: newLoading };
    }
    case 'SET_LOADING': {
      const newLoading = new Set(state.loadingTasks);
      newLoading.add(action.id);
      return { ...state, loadingTasks: newLoading };
    }
    case 'CLEAR_LOADING': {
      const newLoading = new Set(state.loadingTasks);
      newLoading.delete(action.id);
      return { ...state, loadingTasks: newLoading };
    }
    case 'CLEAR_ALL':
      return { ...initialState, loadingTasks: new Set() };
    default:
      return state;
  }
}

interface TaskStoreContextValue {
  state: TaskStoreState;
  loadRootTaskIds: () => void;
  refresh: () => void;
}

const TaskStoreContext = createContext<TaskStoreContextValue | null>(null);

export const TaskStoreProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [state, dispatch] = useReducer(reducer, initialState);
  const fetchedRef = useRef<Set<string>>(new Set());
  const client = useTaskClient();

  const loadTask = useCallback(async (id: string) => {
    if (fetchedRef.current.has(id)) return;
    fetchedRef.current.add(id);

    dispatch({ type: 'SET_LOADING', id });
    const task = await client.getTask(id);
    if (!task) {
      dispatch({ type: 'CLEAR_LOADING', id });
      return;
    }
    dispatch({ type: 'SET_TASK', task });

    // Recursively load children and callbacks
    const idsToLoad = [
      ...task.children_ids,
      ...task.success_callback_ids,
      ...task.error_callback_ids,
    ];
    idsToLoad.forEach(childId => loadTask(childId));
  }, []);

  const loadRootTaskIds = useCallback(async () => {
    dispatch({ type: 'SET_ROOT_LOADING', loading: true });
    const ids = await client.getRootTaskIds();
    dispatch({ type: 'SET_ROOT_IDS', ids });
    ids.forEach(id => loadTask(id));
  }, [loadTask]);

  const refresh = useCallback(() => {
    fetchedRef.current.clear();
    dispatch({ type: 'CLEAR_ALL' });
    loadRootTaskIds();
  }, [loadRootTaskIds]);

  return (
    <TaskStoreContext.Provider value={{ state, loadRootTaskIds, refresh }}>
      {children}
    </TaskStoreContext.Provider>
  );
};

export const useTaskStore = (): TaskStoreContextValue => {
  const ctx = useContext(TaskStoreContext);
  if (!ctx) throw new Error('useTaskStore must be used within TaskStoreProvider');
  return ctx;
};
