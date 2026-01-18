export const chainTaskExample = {
  "mainChain": {
    id: "mainChain",
    name: "Main Process Chain",
    type: "ChainTaskSignature",
    tasks: ["task1", "parallelSwarm", "task3"],
    successCallbacks: ["chainSwarm"],
    errorCallbacks: []
  },
  "task1": {
    id: "task1",
    name: "First Task",
    type: "TaskSignature",
    parent: "mainChain",
    successCallbacks: [],
    errorCallbacks: []
  },
  "parallelSwarm": {
    id: "parallelSwarm",
    name: "Parallel Workers",
    type: "SwarmTaskSignature",
    parent: "mainChain",
    tasks: ["workerA", "workerB", "workerC"],
    successCallbacks: ["parallelSwarm_callback"],
    errorCallbacks: []
  },
  "workerA": {
    id: "workerA",
    name: "Worker A",
    type: "TaskSignature",
    parent: "parallelSwarm",
    successCallbacks: [],
    errorCallbacks: []
  },
  "workerB": {
    id: "workerB",
    name: "Worker B",
    type: "TaskSignature",
    parent: "parallelSwarm",
    successCallbacks: ["workerB_notify"],
    errorCallbacks: ["workerB_error"]
  },
  "workerC": {
    id: "workerC",
    name: "Worker C",
    type: "TaskSignature",
    parent: "parallelSwarm",
    successCallbacks: [],
    errorCallbacks: []
  },
  "task3": {
    id: "task3",
    name: "Third Task",
    type: "TaskSignature",
    parent: "mainChain",
    successCallbacks: [],
    errorCallbacks: []
  },
  "chainSwarm": {
    id: "chainSwarm",
    name: "Parallel Chains",
    type: "SwarmTaskSignature",
    tasks: ["chainA", "chainB"],
    successCallbacks: ["finalTask"],
    errorCallbacks: ["errorHandler"]
  },
  "chainA": {
    id: "chainA",
    name: "Pipeline A",
    type: "ChainTaskSignature",
    parent: "chainSwarm",
    tasks: ["chainA_step1", "chainA_step2"],
    successCallbacks: [],
    errorCallbacks: []
  },
  "chainA_step1": {
    id: "chainA_step1",
    name: "A: Step 1",
    type: "TaskSignature",
    parent: "chainA",
    successCallbacks: ["chainA_step1_success_callback"],
    errorCallbacks: []
  },
  "chainA_step2": {
    id: "chainA_step2",
    name: "A: Step 2",
    type: "TaskSignature",
    parent: "chainA",
    successCallbacks: [],
    errorCallbacks: []
  },
  "chainB": {
    id: "chainB",
    name: "Pipeline B",
    type: "ChainTaskSignature",
    parent: "chainSwarm",
    tasks: ["chainB_step1", "chainB_step2"],
    successCallbacks: [],
    errorCallbacks: []
  },
  "chainB_step1": {
    id: "chainB_step1",
    name: "B: Step 1",
    type: "TaskSignature",
    parent: "chainB",
    successCallbacks: [],
    errorCallbacks: []
  },
  "chainB_step2": {
    id: "chainB_step2",
    name: "B: Step 2",
    type: "TaskSignature",
    parent: "chainB",
    successCallbacks: ["chainB_done_notify"],
    errorCallbacks: []
  },
  "finalTask": {
    id: "finalTask",
    name: "Complete",
    type: "TaskSignature",
    successCallbacks: [],
    errorCallbacks: []
  },
  "errorHandler": {
    id: "errorHandler",
    name: "Handle Chain Error",
    type: "TaskSignature",
    successCallbacks: [],
    errorCallbacks: []
  },
  "chainA_step1_success_callback": {
    id: "chainA_step1_success_callback",
    name: "A: Step 1 Callback",
    type: "TaskSignature",
    successCallbacks: [],
    errorCallbacks: []
  },
  "workerB_notify": {
    id: "workerB_notify",
    name: "Worker B Notify",
    type: "TaskSignature",
    successCallbacks: [],
    errorCallbacks: []
  },
  "workerB_error": {
    id: "workerB_error",
    name: "Worker B Error",
    type: "TaskSignature",
    successCallbacks: [],
    errorCallbacks: []
  },
  "chainB_done_notify": {
    id: "chainB_done_notify",
    name: "Pipeline B Done",
    type: "TaskSignature",
    successCallbacks: [],
    errorCallbacks: []
  },
  "parallelSwarm_callback": {
    id: "parallelSwarm_callback",
    name: "Parallel swarm callback",
    type: "TaskSignature",
    successCallbacks: [],
    errorCallbacks: []
  },

};