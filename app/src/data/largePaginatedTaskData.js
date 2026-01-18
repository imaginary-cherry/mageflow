const generateChildTasks = (parentId, count, prefix = 'task') => {
  const childIds = [];
  const tasks = {};

  for (let i = 1; i <= count; i++) {
    const id = `${parentId}_${prefix}${i}`;
    childIds.push(id);
    tasks[id] = {
      id,
      name: `${prefix.charAt(0).toUpperCase() + prefix.slice(1)} ${i}`,
      type: 'TaskSignature',
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
      type: 'SwarmTaskSignature',
      tasks: swarmChildren,
      successCallbacks: ['swarmComplete'],
      errorCallbacks: [],
      pageSize: 10,
    },
    ...swarmChildTasks,
    swarmComplete: {
      id: 'swarmComplete',
      name: 'Swarm Complete',
      type: 'TaskSignature',
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
      type: 'ChainTaskSignature',
      tasks: chainChildren,
      successCallbacks: ['chainComplete'],
      errorCallbacks: [],
      pageSize: 5,
    },
    ...chainChildTasks,
    chainComplete: {
      id: 'chainComplete',
      name: 'Chain Complete',
      type: 'TaskSignature',
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
      type: 'TaskSignature',
      successCallbacks: ['mixedSwarm'],
      errorCallbacks: [],
    },
    mixedSwarm: {
      id: 'mixedSwarm',
      name: 'Parallel Processing',
      type: 'SwarmTaskSignature',
      tasks: swarmChildren,
      successCallbacks: ['mixedChain'],
      errorCallbacks: [],
      pageSize: 8,
    },
    ...swarmChildTasks,
    mixedChain: {
      id: 'mixedChain',
      name: 'Sequential Pipeline',
      type: 'ChainTaskSignature',
      tasks: chainChildren,
      successCallbacks: ['endTask'],
      errorCallbacks: [],
      pageSize: 4,
    },
    ...chainChildTasks,
    endTask: {
      id: 'endTask',
      name: 'End Process',
      type: 'TaskSignature',
      successCallbacks: [],
      errorCallbacks: [],
    },
  };
};

export const largeSwarmExample = createLargeSwarmExample();
export const largeChainExample = createLargeChainExample();
export const mixedLargeExample = createMixedLargeExample();
