export const TaskTypes = {
  TASK: 'TaskSignature',
  CHAIN: 'ChainTaskSignature',
  SWARM: 'SwarmTaskSignature',
};

export const extractTypeFromKey = (key) => {
  const colonIndex = key.indexOf(':');
  return colonIndex > 0 ? key.substring(0, colonIndex) : null;
};

export const isContainerTask = (task) =>
  task.type === TaskTypes.CHAIN || task.type === TaskTypes.SWARM;

export const hasCallbacks = (task) =>
  task.successCallbacks?.length > 0 || task.errorCallbacks?.length > 0;

export const hasChildren = (task) =>
  isContainerTask(task) && task.tasks?.length > 0;

export const getTotalChildren = (task) =>
  isContainerTask(task) ? (task.tasks?.length || 0) : 0;
