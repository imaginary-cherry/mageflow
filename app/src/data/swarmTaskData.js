export const swarmTaskExample = {
  "startTask": {
    id: "startTask",
    name: "Start Process",
    type: "TaskSignature",
    successCallbacks: ["mainSwarm"],
    errorCallbacks: []
  },
  "mainSwarm": {
    id: "mainSwarm",
    name: "Parallel Workers",
    type: "SwarmTaskSignature",
    tasks: ["worker1", "worker2", "worker3"],
    successCallbacks: ["aggregator"],
    errorCallbacks: ["errorHandler"]
  },
  "worker1": {
    id: "worker1",
    name: "Worker A",
    type: "TaskSignature",
    parent: "mainSwarm",
    successCallbacks: [],
    errorCallbacks: []
  },
  "worker2": {
    id: "worker2",
    name: "Worker B",
    type: "TaskSignature",
    parent: "mainSwarm",
    successCallbacks: [],
    errorCallbacks: []
  },
  "worker3": {
    id: "worker3",
    name: "Worker C",
    type: "TaskSignature",
    parent: "mainSwarm",
    successCallbacks: [],
    errorCallbacks: []
  },
  "aggregator": {
    id: "aggregator",
    name: "Aggregate Results",
    type: "TaskSignature",
    successCallbacks: [],
    errorCallbacks: []
  },
  "errorHandler": {
    id: "errorHandler",
    name: "Handle Swarm Error",
    type: "TaskSignature",
    successCallbacks: [],
    errorCallbacks: []
  }
};

export const mixedTaskExample = {
  "startTask": {
    id: "startTask",
    name: "Initialize",
    type: "TaskSignature",
    successCallbacks: ["mainChain"],
    errorCallbacks: []
  },
  "mainChain": {
    id: "mainChain",
    name: "Sequential Process",
    type: "ChainTaskSignature",
    tasks: ["prepare", "parallelSwarm", "finalize"],
    successCallbacks: ["complete"],
    errorCallbacks: ["errorHandler"]
  },
  "prepare": {
    id: "prepare",
    name: "Prepare Data",
    type: "TaskSignature",
    parent: "mainChain",
    successCallbacks: [],
    errorCallbacks: []
  },
  "parallelSwarm": {
    id: "parallelSwarm",
    name: "Process in Parallel",
    type: "SwarmTaskSignature",
    parent: "mainChain",
    tasks: ["processA", "processB"],
    successCallbacks: [],
    errorCallbacks: []
  },
  "processA": {
    id: "processA",
    name: "Process A",
    type: "TaskSignature",
    parent: "parallelSwarm",
    successCallbacks: [],
    errorCallbacks: []
  },
  "processB": {
    id: "processB",
    name: "Process B",
    type: "TaskSignature",
    parent: "parallelSwarm",
    successCallbacks: [],
    errorCallbacks: []
  },
  "finalize": {
    id: "finalize",
    name: "Finalize",
    type: "TaskSignature",
    parent: "mainChain",
    successCallbacks: [],
    errorCallbacks: []
  },
  "complete": {
    id: "complete",
    name: "Complete",
    type: "TaskSignature",
    successCallbacks: [],
    errorCallbacks: []
  },
  "errorHandler": {
    id: "errorHandler",
    name: "Error Handler",
    type: "TaskSignature",
    successCallbacks: [],
    errorCallbacks: []
  }
};
