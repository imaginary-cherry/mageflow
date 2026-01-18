const generateChildTasks = (parentId, count, prefix = 'task') => {
  const childIds = [];
  const tasks = {};

  for (let i = 1; i <= count; i++) {
    const id = `${parentId}_${prefix}${i}`;
    childIds.push(id);
    tasks[id] = {
      id,
      name: `${prefix.charAt(0).toUpperCase() + prefix.slice(1)} ${i}`,
      type: 'task',
      parent: parentId,
      successCallbacks: [],
      errorCallbacks: [],
    };
  }

  return { childIds, tasks };
};

const createLargeSwarmExample = () => {
  const { childIds: swarmChildren, tasks: swarmChildTasks } = generateChildTasks('largeSwarm', 50, 'worker');

  return {
    largeSwarm: {
      id: 'largeSwarm',
      name: 'Large Parallel Swarm',
      type: 'swarm',
      children: swarmChildren,
      successCallbacks: ['swarmComplete'],
      errorCallbacks: [],
      pageSize: 10,
    },
    ...swarmChildTasks,
    swarmComplete: {
      id: 'swarmComplete',
      name: 'Swarm Complete',
      type: 'task',
      successCallbacks: [],
      errorCallbacks: [],
    },
  };
};

const createLargeChainExample = () => {
  const { childIds: chainChildren, tasks: chainChildTasks } = generateChildTasks('largeChain', 30, 'step');

  return {
    largeChain: {
      id: 'largeChain',
      name: 'Large Sequential Chain',
      type: 'chain',
      children: chainChildren,
      successCallbacks: ['chainComplete'],
      errorCallbacks: [],
      pageSize: 5,
    },
    ...chainChildTasks,
    chainComplete: {
      id: 'chainComplete',
      name: 'Chain Complete',
      type: 'task',
      successCallbacks: [],
      errorCallbacks: [],
    },
  };
};

const createMixedLargeExample = () => {
  const { childIds: swarmChildren, tasks: swarmChildTasks } = generateChildTasks('mixedSwarm', 25, 'parallel');
  const { childIds: chainChildren, tasks: chainChildTasks } = generateChildTasks('mixedChain', 15, 'sequential');

  return {
    startTask: {
      id: 'startTask',
      name: 'Start Process',
      type: 'task',
      successCallbacks: ['mixedSwarm'],
      errorCallbacks: [],
    },
    mixedSwarm: {
      id: 'mixedSwarm',
      name: 'Parallel Processing',
      type: 'swarm',
      children: swarmChildren,
      successCallbacks: ['mixedChain'],
      errorCallbacks: [],
      pageSize: 8,
    },
    ...swarmChildTasks,
    mixedChain: {
      id: 'mixedChain',
      name: 'Sequential Pipeline',
      type: 'chain',
      children: chainChildren,
      successCallbacks: ['endTask'],
      errorCallbacks: [],
      pageSize: 4,
    },
    ...chainChildTasks,
    endTask: {
      id: 'endTask',
      name: 'End Process',
      type: 'task',
      successCallbacks: [],
      errorCallbacks: [],
    },
  };
};

export const largeSwarmExample = createLargeSwarmExample();
export const largeChainExample = createLargeChainExample();
export const mixedLargeExample = createMixedLargeExample();
