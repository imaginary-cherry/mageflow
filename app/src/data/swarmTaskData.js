export const swarmTaskExample = {
  "startTask": {
    id: "startTask",
    name: "Start Process",
    type: "task",
    successCallbacks: ["mainSwarm"],
    errorCallbacks: []
  },
  "mainSwarm": {
    id: "mainSwarm",
    name: "Parallel Workers",
    type: "swarm",
    children: ["worker1", "worker2", "worker3"],
    successCallbacks: ["aggregator"],
    errorCallbacks: ["errorHandler"]
  },
  "worker1": {
    id: "worker1",
    name: "Worker A",
    type: "task",
    parent: "mainSwarm",
    successCallbacks: [],
    errorCallbacks: []
  },
  "worker2": {
    id: "worker2",
    name: "Worker B",
    type: "task",
    parent: "mainSwarm",
    successCallbacks: [],
    errorCallbacks: []
  },
  "worker3": {
    id: "worker3",
    name: "Worker C",
    type: "task",
    parent: "mainSwarm",
    successCallbacks: [],
    errorCallbacks: []
  },
  "aggregator": {
    id: "aggregator",
    name: "Aggregate Results",
    type: "task",
    successCallbacks: [],
    errorCallbacks: []
  },
  "errorHandler": {
    id: "errorHandler",
    name: "Handle Swarm Error",
    type: "task",
    successCallbacks: [],
    errorCallbacks: []
  }
};

export const mixedTaskExample = {
  "startTask": {
    id: "startTask",
    name: "Initialize",
    type: "task",
    successCallbacks: ["mainChain"],
    errorCallbacks: []
  },
  "mainChain": {
    id: "mainChain",
    name: "Sequential Process",
    type: "chain",
    children: ["prepare", "parallelSwarm", "finalize"],
    successCallbacks: ["complete"],
    errorCallbacks: ["errorHandler"]
  },
  "prepare": {
    id: "prepare",
    name: "Prepare Data",
    type: "task",
    parent: "mainChain",
    successCallbacks: [],
    errorCallbacks: []
  },
  "parallelSwarm": {
    id: "parallelSwarm",
    name: "Process in Parallel",
    type: "swarm",
    parent: "mainChain",
    children: ["processA", "processB"],
    successCallbacks: [],
    errorCallbacks: []
  },
  "processA": {
    id: "processA",
    name: "Process A",
    type: "task",
    parent: "parallelSwarm",
    successCallbacks: [],
    errorCallbacks: []
  },
  "processB": {
    id: "processB",
    name: "Process B",
    type: "task",
    parent: "parallelSwarm",
    successCallbacks: [],
    errorCallbacks: []
  },
  "finalize": {
    id: "finalize",
    name: "Finalize",
    type: "task",
    parent: "mainChain",
    successCallbacks: [],
    errorCallbacks: []
  },
  "complete": {
    id: "complete",
    name: "Complete",
    type: "task",
    successCallbacks: [],
    errorCallbacks: []
  },
  "errorHandler": {
    id: "errorHandler",
    name: "Error Handler",
    type: "task",
    successCallbacks: [],
    errorCallbacks: []
  }
};
