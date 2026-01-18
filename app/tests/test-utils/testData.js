export const simpleLinearTasks = {
  "task1": {
    id: "task1",
    name: "Start",
    type: "TaskSignature",
    successCallbacks: ["task2"],
    errorCallbacks: []
  },
  "task2": {
    id: "task2",
    name: "Middle",
    type: "TaskSignature",
    successCallbacks: ["task3"],
    errorCallbacks: []
  },
  "task3": {
    id: "task3",
    name: "End",
    type: "TaskSignature",
    successCallbacks: [],
    errorCallbacks: []
  }
};

export const branchingTasks = {
  "root": {
    id: "root",
    name: "Root Task",
    type: "TaskSignature",
    successCallbacks: ["branch1", "branch2"],
    errorCallbacks: ["error1"]
  },
  "branch1": {
    id: "branch1",
    name: "Branch A",
    type: "TaskSignature",
    successCallbacks: ["end1"],
    errorCallbacks: []
  },
  "branch2": {
    id: "branch2",
    name: "Branch B", 
    type: "TaskSignature",
    successCallbacks: ["end2"],
    errorCallbacks: []
  },
  "end1": {
    id: "end1",
    name: "End A",
    type: "TaskSignature",
    successCallbacks: [],
    errorCallbacks: []
  },
  "end2": {
    id: "end2",
    name: "End B",
    type: "TaskSignature",
    successCallbacks: [],
    errorCallbacks: []
  },
  "error1": {
    id: "error1",
    name: "Error Handler",
    type: "TaskSignature",
    successCallbacks: [],
    errorCallbacks: []
  }
};

export const variableSizeTasks = {
  "small": {
    id: "small",
    name: "S",
    type: "TaskSignature",
    width: 80,
    height: 40,
    successCallbacks: ["medium", "large"],
    errorCallbacks: []
  },
  "medium": {
    id: "medium",
    name: "Medium Task Name",
    type: "TaskSignature",
    successCallbacks: ["end"],
    errorCallbacks: []
  },
  "large": {
    id: "large",
    name: "Very Long Task Name That Should Take More Space",
    type: "TaskSignature",
    width: 300,
    height: 80,
    successCallbacks: ["end"],
    errorCallbacks: []
  },
  "end": {
    id: "end",
    name: "Complete",
    type: "TaskSignature",
    successCallbacks: [],
    errorCallbacks: []
  }
};

export const complexWorkflowTasks = {
  "init": {
    id: "init",
    name: "Initialize",
    type: "TaskSignature",
    successCallbacks: ["config", "db"],
    errorCallbacks: ["errorInit"]
  },
  "config": {
    id: "config",
    name: "Load Config",
    type: "TaskSignature",
    successCallbacks: ["validate"],
    errorCallbacks: ["errorConfig"]
  },
  "db": {
    id: "db",
    name: "Connect Database",
    type: "TaskSignature",
    width: 200,
    height: 70,
    successCallbacks: ["migrate", "cache"],
    errorCallbacks: ["errorDb"]
  },
  "validate": {
    id: "validate",
    name: "Validate",
    type: "TaskSignature",
    successCallbacks: ["start"],
    errorCallbacks: []
  },
  "migrate": {
    id: "migrate",
    name: "Run Migrations",
    type: "TaskSignature",
    successCallbacks: ["ready1"],
    errorCallbacks: []
  },
  "cache": {
    id: "cache",
    name: "Cache",
    type: "TaskSignature",
    width: 120,
    height: 50,
    successCallbacks: ["ready2"],
    errorCallbacks: []
  },
  "start": {
    id: "start",
    name: "Start Services",
    type: "TaskSignature",
    successCallbacks: ["complete"],
    errorCallbacks: []
  },
  "ready1": {
    id: "ready1",
    name: "DB Ready",
    type: "TaskSignature",
    successCallbacks: [],
    errorCallbacks: []
  },
  "ready2": {
    id: "ready2",
    name: "Cache Ready",
    type: "TaskSignature",
    successCallbacks: [],
    errorCallbacks: []
  },
  "complete": {
    id: "complete",
    name: "System Ready",
    type: "TaskSignature",
    successCallbacks: [],
    errorCallbacks: []
  },
  "errorInit": {
    id: "errorInit",
    name: "Init Error",
    type: "TaskSignature",
    successCallbacks: ["errorNotify"],
    errorCallbacks: []
  },
  "errorConfig": {
    id: "errorConfig",
    name: "Config Error",
    type: "TaskSignature",
    successCallbacks: [],
    errorCallbacks: []
  },
  "errorDb": {
    id: "errorDb",
    name: "DB Error",
    type: "TaskSignature",
    successCallbacks: ["errorNotify"],
    errorCallbacks: []
  },
  "errorNotify": {
    id: "errorNotify",
    name: "Notify Admin",
    type: "TaskSignature",
    successCallbacks: [],
    errorCallbacks: []
  }
};

export const currentTasksLayoutSnapshot = {
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
