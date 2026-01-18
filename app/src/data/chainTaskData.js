export const chainTaskExample = {
  "mainChain": {
    id: "mainChain",
    name: "Main Process Chain",
    type: "chain",
    children: ["task1", "parallelSwarm", "task3"],
    successCallbacks: ["chainSwarm"],
    errorCallbacks: []
  },
  "task1": {
    id: "task1",
    name: "First Task",
    type: "task",
    parent: "mainChain",
    successCallbacks: [],
    errorCallbacks: []
  },
  "parallelSwarm": {
    id: "parallelSwarm",
    name: "Parallel Workers",
    type: "swarm",
    parent: "mainChain",
    children: ["workerA", "workerB", "workerC"],
    successCallbacks: ["parallelSwarm_callback"],
    errorCallbacks: []
  },
  "workerA": {
    id: "workerA",
    name: "Worker A",
    type: "task",
    parent: "parallelSwarm",
    successCallbacks: [],
    errorCallbacks: []
  },
  "workerB": {
    id: "workerB",
    name: "Worker B",
    type: "task",
    parent: "parallelSwarm",
    successCallbacks: ["workerB_notify"],
    errorCallbacks: ["workerB_error"]
  },
  "workerC": {
    id: "workerC",
    name: "Worker C",
    type: "task",
    parent: "parallelSwarm",
    successCallbacks: [],
    errorCallbacks: []
  },
  "task3": {
    id: "task3",
    name: "Third Task",
    type: "task",
    parent: "mainChain",
    successCallbacks: [],
    errorCallbacks: []
  },
  "chainSwarm": {
    id: "chainSwarm",
    name: "Parallel Chains",
    type: "swarm",
    children: ["chainA", "chainB"],
    successCallbacks: ["finalTask"],
    errorCallbacks: ["errorHandler"]
  },
  "chainA": {
    id: "chainA",
    name: "Pipeline A",
    type: "chain",
    parent: "chainSwarm",
    children: ["chainA_step1", "chainA_step2"],
    successCallbacks: [],
    errorCallbacks: []
  },
  "chainA_step1": {
    id: "chainA_step1",
    name: "A: Step 1",
    type: "task",
    parent: "chainA",
    successCallbacks: ["chainA_step1_success_callback"],
    errorCallbacks: []
  },
  "chainA_step2": {
    id: "chainA_step2",
    name: "A: Step 2",
    type: "task",
    parent: "chainA",
    successCallbacks: [],
    errorCallbacks: []
  },
  "chainB": {
    id: "chainB",
    name: "Pipeline B",
    type: "chain",
    parent: "chainSwarm",
    children: ["chainB_step1", "chainB_step2"],
    successCallbacks: [],
    errorCallbacks: []
  },
  "chainB_step1": {
    id: "chainB_step1",
    name: "B: Step 1",
    type: "task",
    parent: "chainB",
    successCallbacks: [],
    errorCallbacks: []
  },
  "chainB_step2": {
    id: "chainB_step2",
    name: "B: Step 2",
    type: "task",
    parent: "chainB",
    successCallbacks: ["chainB_done_notify"],
    errorCallbacks: []
  },
  "finalTask": {
    id: "finalTask",
    name: "Complete",
    type: "task",
    successCallbacks: [],
    errorCallbacks: []
  },
  "errorHandler": {
    id: "errorHandler",
    name: "Handle Chain Error",
    type: "task",
    successCallbacks: [],
    errorCallbacks: []
  },
  "chainA_step1_success_callback": {
    id: "chainA_step1_success_callback",
    name: "A: Step 1 Callback",
    type: "task",
    successCallbacks: [],
    errorCallbacks: []
  },
  "workerB_notify": {
    id: "workerB_notify",
    name: "Worker B Notify",
    type: "task",
    successCallbacks: [],
    errorCallbacks: []
  },
  "workerB_error": {
    id: "workerB_error",
    name: "Worker B Error",
    type: "task",
    successCallbacks: [],
    errorCallbacks: []
  },
  "chainB_done_notify": {
    id: "chainB_done_notify",
    name: "Pipeline B Done",
    type: "task",
    successCallbacks: [],
    errorCallbacks: []
  },
  "parallelSwarm_callback": {
    id: "parallelSwarm_callback",
    name: "Parallel swarm callback",
    type: "task",
    successCallbacks: [],
    errorCallbacks: []
  },

};