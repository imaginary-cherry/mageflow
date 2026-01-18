export const sampleTasks = {
  "task1": {
    id: "task1",
    name: "Initialize System",
    type: "task",
    successCallbacks: ["task2", "task3"],
    errorCallbacks: ["errorHandler1"]
  },
  "task2": {
    id: "task2",
    name: "Load Configuration",
    type: "task",
    successCallbacks: ["task4"],
    errorCallbacks: ["errorHandler2"]
  },
  "task3": {
    id: "task3",
    name: "Connect to Primary Database Server and Initialize Connection Pool",
    type: "task",
    width: 280,
    height: 80,
    successCallbacks: ["task5", "task6"],
    errorCallbacks: ["errorHandler3"]
  },
  "task4": {
    id: "task4",
    name: "Validate Config",
    type: "task",
    successCallbacks: ["task7"],
    errorCallbacks: ["errorHandler4"]
  },
  "task5": {
    id: "task5",
    name: "Cache",
    type: "task",
    width: 120,
    height: 50,
    successCallbacks: ["task8"],
    errorCallbacks: ["errorHandler5"]
  },
  "task6": {
    id: "task6",
    name: "Init Connection Pool",
    type: "task",
    successCallbacks: ["task9"],
    errorCallbacks: ["errorHandler6"]
  },
  "task7": {
    id: "task7",
    name: "Start API Server",
    type: "task",
    successCallbacks: ["task10"],
    errorCallbacks: []
  },
  "task8": {
    id: "task8",
    name: "Warm Cache",
    type: "task",
    successCallbacks: ["task11"],
    errorCallbacks: []
  },
  "task9": {
    id: "task9",
    name: "Run Database Migrations and Schema Updates",
    type: "task",
    width: 250,
    height: 70,
    successCallbacks: ["task12"],
    errorCallbacks: []
  },
  "task10": {
    id: "task10",
    name: "API Ready",
    type: "task",
    successCallbacks: [],
    errorCallbacks: []
  },
  "task11": {
    id: "task11",
    name: "Cache Ready",
    type: "task",
    successCallbacks: [],
    errorCallbacks: []
  },
  "task12": {
    id: "task12",
    name: "DB Ready",
    type: "task",
    successCallbacks: [],
    errorCallbacks: []
  },
  "errorHandler1": {
    id: "errorHandler1",
    name: "Log Init Error",
    type: "task",
    successCallbacks: ["errorHandler7"],
    errorCallbacks: []
  },
  "errorHandler2": {
    id: "errorHandler2",
    name: "Config Error",
    type: "task",
    successCallbacks: [],
    errorCallbacks: []
  },
  "errorHandler3": {
    id: "errorHandler3",
    name: "DB Connection Error",
    type: "task",
    successCallbacks: ["errorHandler8"],
    errorCallbacks: []
  },
  "errorHandler4": {
    id: "errorHandler4",
    name: "Invalid Config",
    type: "task",
    successCallbacks: [],
    errorCallbacks: []
  },
  "errorHandler5": {
    id: "errorHandler5",
    name: "Cache Setup Failed",
    type: "task",
    successCallbacks: [],
    errorCallbacks: []
  },
  "errorHandler6": {
    id: "errorHandler6",
    name: "Pool Init Failed",
    type: "task",
    successCallbacks: [],
    errorCallbacks: []
  },
  "errorHandler7": {
    id: "errorHandler7",
    name: "Notify Admin",
    type: "task",
    successCallbacks: [],
    errorCallbacks: []
  },
  "errorHandler8": {
    id: "errorHandler8",
    name: "Rollback & Notify",
    type: "task",
    successCallbacks: [],
    errorCallbacks: []
  }
};