export const sampleTasks = {
  "task1": {
    id: "task1",
    name: "Initialize System",
    type: "TaskSignature",
    successCallbacks: ["task2", "task3"],
    errorCallbacks: ["errorHandler1"]
  },
  "task2": {
    id: "task2",
    name: "Load Configuration",
    type: "TaskSignature",
    successCallbacks: ["task4"],
    errorCallbacks: ["errorHandler2"]
  },
  "task3": {
    id: "task3",
    name: "Connect to Primary Database Server and Initialize Connection Pool",
    type: "TaskSignature",
    width: 280,
    height: 80,
    successCallbacks: ["task5", "task6"],
    errorCallbacks: ["errorHandler3"]
  },
  "task4": {
    id: "task4",
    name: "Validate Config",
    type: "TaskSignature",
    successCallbacks: ["task7"],
    errorCallbacks: ["errorHandler4"]
  },
  "task5": {
    id: "task5",
    name: "Cache",
    type: "TaskSignature",
    width: 120,
    height: 50,
    successCallbacks: ["task8"],
    errorCallbacks: ["errorHandler5"]
  },
  "task6": {
    id: "task6",
    name: "Init Connection Pool",
    type: "TaskSignature",
    successCallbacks: ["task9"],
    errorCallbacks: ["errorHandler6"]
  },
  "task7": {
    id: "task7",
    name: "Start API Server",
    type: "TaskSignature",
    successCallbacks: ["task10"],
    errorCallbacks: []
  },
  "task8": {
    id: "task8",
    name: "Warm Cache",
    type: "TaskSignature",
    successCallbacks: ["task11"],
    errorCallbacks: []
  },
  "task9": {
    id: "task9",
    name: "Run Database Migrations and Schema Updates",
    type: "TaskSignature",
    width: 250,
    height: 70,
    successCallbacks: ["task12"],
    errorCallbacks: []
  },
  "task10": {
    id: "task10",
    name: "API Ready",
    type: "TaskSignature",
    successCallbacks: [],
    errorCallbacks: []
  },
  "task11": {
    id: "task11",
    name: "Cache Ready",
    type: "TaskSignature",
    successCallbacks: [],
    errorCallbacks: []
  },
  "task12": {
    id: "task12",
    name: "DB Ready",
    type: "TaskSignature",
    successCallbacks: [],
    errorCallbacks: []
  },
  "errorHandler1": {
    id: "errorHandler1",
    name: "Log Init Error",
    type: "TaskSignature",
    successCallbacks: ["errorHandler7"],
    errorCallbacks: []
  },
  "errorHandler2": {
    id: "errorHandler2",
    name: "Config Error",
    type: "TaskSignature",
    successCallbacks: [],
    errorCallbacks: []
  },
  "errorHandler3": {
    id: "errorHandler3",
    name: "DB Connection Error",
    type: "TaskSignature",
    successCallbacks: ["errorHandler8"],
    errorCallbacks: []
  },
  "errorHandler4": {
    id: "errorHandler4",
    name: "Invalid Config",
    type: "TaskSignature",
    successCallbacks: [],
    errorCallbacks: []
  },
  "errorHandler5": {
    id: "errorHandler5",
    name: "Cache Setup Failed",
    type: "TaskSignature",
    successCallbacks: [],
    errorCallbacks: []
  },
  "errorHandler6": {
    id: "errorHandler6",
    name: "Pool Init Failed",
    type: "TaskSignature",
    successCallbacks: [],
    errorCallbacks: []
  },
  "errorHandler7": {
    id: "errorHandler7",
    name: "Notify Admin",
    type: "TaskSignature",
    successCallbacks: [],
    errorCallbacks: []
  },
  "errorHandler8": {
    id: "errorHandler8",
    name: "Rollback & Notify",
    type: "TaskSignature",
    successCallbacks: [],
    errorCallbacks: []
  }
};