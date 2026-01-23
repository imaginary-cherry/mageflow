# React Graph Visualization Architecture

## Overview

This document outlines the architecture for a React-based workflow visualization system optimized for loading and rendering very large task graphs efficiently.

## Key Design Principles

1. **Progressive Loading** - Load data in layers (root → callbacks → subtasks)
2. **Pagination** - Never load all subtasks at once
3. **Normalized State** - Flat data structure for efficient updates
4. **Selective Re-rendering** - Components only re-render when their specific data changes
5. **Dimension Calculation** - Each node calculates its own dimensions
6. **Virtualization** - Only render visible nodes in extremely large graphs

---

## Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           SERVER (Python/FastAPI)                        │
├─────────────────────────────────────────────────────────────────────────┤
│  GET /workflows/roots          → Returns root task IDs + basic info     │
│  GET /tasks/:id                → Returns single task with metadata      │
│  GET /tasks/:id/callbacks      → Returns callback task IDs              │
│  GET /tasks/:id/subtasks       → Returns paginated subtask IDs          │
│  GET /tasks/batch              → Returns multiple tasks by IDs          │
│  WS  /tasks/subscribe/:id      → Real-time updates for task status      │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         REACT DATA LAYER                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Normalized Store (Zustand)                     │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │   │
│  │  │   tasks: {}     │  │  edges: {}      │  │  ui: {}         │  │   │
│  │  │   [id]: Task    │  │  [id]: Edge     │  │  expandedNodes  │  │   │
│  │  │                 │  │                 │  │  selectedNode   │  │   │
│  │  │                 │  │                 │  │  pagination     │  │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘  │   │
│  │                                                                    │   │
│  │  ┌─────────────────────────────────────────────────────────────┐  │   │
│  │  │                    Derived Data (Selectors)                   │  │   │
│  │  │  - getTaskById(id)      → Single task, memoized               │  │   │
│  │  │  - getTaskChildren(id)  → Child IDs only, memoized            │  │   │
│  │  │  - getVisibleNodes()    → Nodes in viewport, memoized         │  │   │
│  │  │  - getGraphForRoot(id)  → Full graph structure, memoized      │  │   │
│  │  └─────────────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         REACT COMPONENT LAYER                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  <WorkflowViewer>                                                  │   │
│  │    ├── <WorkflowTabs>        (root task tabs)                     │   │
│  │    ├── <GraphCanvas>         (react-flow/cytoscape container)     │   │
│  │    │     ├── <TaskNode>      (individual task - memo'd)           │   │
│  │    │     │     ├── <NodeHeader>                                    │   │
│  │    │     │     ├── <NodeContent>                                   │   │
│  │    │     │     └── <ExpandButton>                                  │   │
│  │    │     ├── <SwarmNode>     (swarm container - memo'd)           │   │
│  │    │     │     └── <PaginatedChildren>                             │   │
│  │    │     ├── <ChainNode>     (chain container - memo'd)           │   │
│  │    │     │     └── <PaginatedChildren>                             │   │
│  │    │     └── <EdgeComponent> (connection lines)                    │   │
│  │    └── <TaskInfoPanel>       (selected task details)              │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Normalized State Store

### Why Normalized?

Instead of nested data like:
```javascript
// BAD - Nested structure
{
  rootTask: {
    id: 'task1',
    subtasks: [
      { id: 'task2', subtasks: [...] },
      { id: 'task3', subtasks: [...] }
    ]
  }
}
```

Use flat, normalized structure:
```javascript
// GOOD - Normalized structure
{
  tasks: {
    'task1': { id: 'task1', type: 'swarm', subtaskIds: ['task2', 'task3'], ... },
    'task2': { id: 'task2', type: 'task', ... },
    'task3': { id: 'task3', type: 'chain', subtaskIds: ['task4', 'task5'], ... },
    // ...
  },
  edges: {
    'edge1': { id: 'edge1', source: 'task1', target: 'task2', type: 'success' },
    // ...
  }
}
```

**Benefits:**
- Update a single task without recreating the entire tree
- O(1) lookup for any task
- Easy to add/remove tasks
- Components subscribe to specific task IDs only

### Store Implementation (Zustand)

```typescript
// stores/graphStore.ts
import { create } from 'zustand'
import { immer } from 'zustand/middleware/immer'

interface Task {
  id: string
  type: 'task' | 'chain' | 'swarm' | 'batch_item'
  name: string
  status: 'pending' | 'active' | 'completed' | 'failed'
  parentId: string | null

  // Relationships (IDs only, not full objects)
  subtaskIds: string[]
  successCallbackIds: string[]
  errorCallbackIds: string[]

  // Metadata
  kwargs: Record<string, unknown>
  createdAt: string

  // Loading state for this specific task
  loadingState: 'idle' | 'loading' | 'loaded' | 'error'
  subtasksLoadingState: 'idle' | 'loading' | 'loaded' | 'error'

  // Pagination for subtasks
  subtasksPagination: {
    currentPage: number
    pageSize: number
    totalCount: number
    loadedPages: number[] // Which pages are loaded
  }

  // Dimensions (calculated by component, stored for layout)
  dimensions: {
    width: number
    height: number
    calculatedAt: number // timestamp
  } | null
}

interface Edge {
  id: string
  source: string
  target: string
  type: 'success' | 'error' | 'subtask'
}

interface UIState {
  selectedTaskId: string | null
  expandedNodeIds: Set<string>
  activeRootId: string | null
  viewport: { x: number; y: number; zoom: number }
}

interface GraphStore {
  // Normalized data
  tasks: Record<string, Task>
  edges: Record<string, Edge>
  rootTaskIds: string[]

  // UI state
  ui: UIState

  // Actions - these use immer for immutable updates
  actions: {
    // Task operations
    setTask: (task: Task) => void
    setTasks: (tasks: Task[]) => void
    updateTaskStatus: (id: string, status: Task['status']) => void
    updateTaskDimensions: (id: string, dimensions: Task['dimensions']) => void

    // Subtask pagination
    setSubtaskPage: (taskId: string, page: number) => void
    appendSubtaskIds: (taskId: string, ids: string[], page: number) => void

    // Edge operations
    setEdge: (edge: Edge) => void
    setEdges: (edges: Edge[]) => void

    // UI operations
    selectTask: (id: string | null) => void
    toggleNodeExpanded: (id: string) => void
    setActiveRoot: (id: string) => void
    setViewport: (viewport: UIState['viewport']) => void

    // Batch operations
    loadRootTasks: () => Promise<void>
    loadTaskCallbacks: (taskId: string) => Promise<void>
    loadTaskSubtasks: (taskId: string, page: number) => Promise<void>
  }
}

export const useGraphStore = create<GraphStore>()(
  immer((set, get) => ({
    tasks: {},
    edges: {},
    rootTaskIds: [],
    ui: {
      selectedTaskId: null,
      expandedNodeIds: new Set(),
      activeRootId: null,
      viewport: { x: 0, y: 0, zoom: 1 },
    },

    actions: {
      setTask: (task) => set((state) => {
        state.tasks[task.id] = task
      }),

      setTasks: (tasks) => set((state) => {
        tasks.forEach(task => {
          state.tasks[task.id] = task
        })
      }),

      updateTaskStatus: (id, status) => set((state) => {
        if (state.tasks[id]) {
          state.tasks[id].status = status
        }
      }),

      updateTaskDimensions: (id, dimensions) => set((state) => {
        if (state.tasks[id]) {
          state.tasks[id].dimensions = dimensions
        }
      }),

      // ... more actions
    }
  }))
)
```

---

## 2. Memoized Selectors

Selectors derive data from the store and are memoized to prevent unnecessary recalculations.

```typescript
// selectors/taskSelectors.ts
import { useGraphStore } from '../stores/graphStore'
import { useMemo } from 'react'
import { shallow } from 'zustand/shallow'

// Get a single task - only re-renders when THIS task changes
export function useTask(taskId: string) {
  return useGraphStore(
    (state) => state.tasks[taskId],
    shallow // shallow comparison for the task object
  )
}

// Get only the IDs of children - prevents re-render when children data changes
export function useTaskChildIds(taskId: string): string[] {
  return useGraphStore(
    (state) => state.tasks[taskId]?.subtaskIds ?? [],
    shallow
  )
}

// Get edges for a specific task
export function useTaskEdges(taskId: string) {
  return useGraphStore(
    (state) => Object.values(state.edges).filter(
      edge => edge.source === taskId || edge.target === taskId
    ),
    shallow
  )
}

// Get the pagination state for a task's subtasks
export function useSubtaskPagination(taskId: string) {
  return useGraphStore(
    (state) => state.tasks[taskId]?.subtasksPagination,
    shallow
  )
}

// Get tasks for current visible page only
export function useVisibleSubtasks(taskId: string) {
  const task = useTask(taskId)
  const allTasks = useGraphStore((state) => state.tasks)

  return useMemo(() => {
    if (!task) return []

    const { currentPage, pageSize, loadedPages } = task.subtasksPagination
    const startIdx = currentPage * pageSize
    const endIdx = startIdx + pageSize

    // Get IDs for current page
    const pageIds = task.subtaskIds.slice(startIdx, endIdx)

    // Return full task objects for these IDs
    return pageIds.map(id => allTasks[id]).filter(Boolean)
  }, [task?.subtaskIds, task?.subtasksPagination, allTasks])
}
```

---

## 3. Progressive Loading Strategy

### Loading Phases

```
Phase 1: Root Tasks
├── Fetch root task IDs from server
├── Fetch basic info for each root task (name, type, status)
└── Display tabs and first root graph skeleton

Phase 2: Callbacks (BFS from root)
├── For active root task:
│   ├── Fetch success callback IDs
│   ├── Fetch error callback IDs
│   └── Fetch basic info for callbacks
├── Create edges to callbacks
└── Continue BFS until all callbacks loaded

Phase 3: Subtasks (On-demand / Lazy)
├── When user expands a swarm/chain:
│   ├── Fetch first page of subtask IDs
│   ├── Fetch basic info for first page tasks
│   └── Display with pagination controls
├── Pre-fetch next page in background
└── Check subtasks for callbacks (external references)

Phase 4: Nested Subtasks (Recursive)
├── If subtask is swarm/chain:
│   └── Repeat Phase 3 for that subtask
└── If subtask has callbacks outside parent:
    └── Load those callbacks and connect edges
```

### Loading Hook Implementation

```typescript
// hooks/useProgressiveLoader.ts
import { useCallback, useEffect, useRef } from 'react'
import { useGraphStore } from '../stores/graphStore'
import { api } from '../api/client'

interface LoaderState {
  loadedTaskIds: Set<string>
  pendingTaskIds: Set<string>
  loadingTaskIds: Set<string>
}

export function useProgressiveLoader(rootTaskId: string | null) {
  const actions = useGraphStore((state) => state.actions)
  const tasks = useGraphStore((state) => state.tasks)

  const loaderState = useRef<LoaderState>({
    loadedTaskIds: new Set(),
    pendingTaskIds: new Set(),
    loadingTaskIds: new Set(),
  })

  // Phase 1: Load root tasks
  const loadRoots = useCallback(async () => {
    const rootIds = await api.getRootTaskIds()
    const rootTasks = await api.getTasksBatch(rootIds)

    actions.setTasks(rootTasks.map(t => ({
      ...t,
      loadingState: 'loaded',
      subtasksLoadingState: 'idle',
    })))

    rootIds.forEach(id => loaderState.current.loadedTaskIds.add(id))

    return rootIds
  }, [actions])

  // Phase 2: Load callbacks for a task (BFS)
  const loadCallbacks = useCallback(async (taskId: string) => {
    const state = loaderState.current

    if (state.loadedTaskIds.has(`callbacks:${taskId}`)) return
    state.loadingTaskIds.add(`callbacks:${taskId}`)

    try {
      const task = tasks[taskId]
      if (!task) return

      // Get callback IDs
      const callbackIds = [
        ...task.successCallbackIds,
        ...task.errorCallbackIds,
      ].filter(id => !state.loadedTaskIds.has(id))

      if (callbackIds.length === 0) return

      // Batch load callback tasks
      const callbackTasks = await api.getTasksBatch(callbackIds)
      actions.setTasks(callbackTasks)

      // Create edges
      const edges = [
        ...task.successCallbackIds.map(targetId => ({
          id: `${taskId}->${targetId}:success`,
          source: taskId,
          target: targetId,
          type: 'success' as const,
        })),
        ...task.errorCallbackIds.map(targetId => ({
          id: `${taskId}->${targetId}:error`,
          source: taskId,
          target: targetId,
          type: 'error' as const,
        })),
      ]
      actions.setEdges(edges)

      // Mark loaded and queue callbacks for their own callback loading
      callbackIds.forEach(id => {
        state.loadedTaskIds.add(id)
        state.pendingTaskIds.add(id) // Queue for callback loading
      })

      state.loadedTaskIds.add(`callbacks:${taskId}`)
    } finally {
      state.loadingTaskIds.delete(`callbacks:${taskId}`)
    }
  }, [tasks, actions])

  // Phase 3: Load subtasks with pagination
  const loadSubtasks = useCallback(async (
    taskId: string,
    page: number = 0,
    pageSize: number = 20
  ) => {
    const state = loaderState.current
    const cacheKey = `subtasks:${taskId}:${page}`

    if (state.loadedTaskIds.has(cacheKey)) return
    state.loadingTaskIds.add(cacheKey)

    try {
      // Fetch paginated subtask IDs
      const response = await api.getTaskSubtasks(taskId, { page, pageSize })

      // Batch load subtask details
      const subtaskDetails = await api.getTasksBatch(response.taskIds)
      actions.setTasks(subtaskDetails)

      // Update parent task with subtask IDs for this page
      actions.appendSubtaskIds(taskId, response.taskIds, page)

      // Create parent-child edges
      const edges = response.taskIds.map(subtaskId => ({
        id: `${taskId}->${subtaskId}:subtask`,
        source: taskId,
        target: subtaskId,
        type: 'subtask' as const,
      }))
      actions.setEdges(edges)

      // Mark loaded
      response.taskIds.forEach(id => state.loadedTaskIds.add(id))
      state.loadedTaskIds.add(cacheKey)

      // Check subtasks for external callbacks
      for (const subtask of subtaskDetails) {
        const externalCallbacks = [
          ...subtask.successCallbackIds,
          ...subtask.errorCallbackIds,
        ].filter(cbId => !isDescendantOf(cbId, taskId, tasks))

        if (externalCallbacks.length > 0) {
          state.pendingTaskIds.add(subtask.id)
        }
      }
    } finally {
      state.loadingTaskIds.delete(cacheKey)
    }
  }, [tasks, actions])

  // BFS processor for pending tasks
  useEffect(() => {
    const processPending = async () => {
      const state = loaderState.current

      while (state.pendingTaskIds.size > 0) {
        const taskId = state.pendingTaskIds.values().next().value
        state.pendingTaskIds.delete(taskId)

        await loadCallbacks(taskId)

        // Small delay to prevent overwhelming the server
        await new Promise(resolve => setTimeout(resolve, 50))
      }
    }

    processPending()
  }, [loadCallbacks])

  return {
    loadRoots,
    loadCallbacks,
    loadSubtasks,
    isLoading: loaderState.current.loadingTaskIds.size > 0,
  }
}

// Helper to check if a task is a descendant of a parent
function isDescendantOf(
  taskId: string,
  parentId: string,
  tasks: Record<string, Task>
): boolean {
  let current = tasks[taskId]
  while (current) {
    if (current.parentId === parentId) return true
    if (!current.parentId) return false
    current = tasks[current.parentId]
  }
  return false
}
```

---

## 4. Component Architecture

### Memoized Node Components

Each node component is memoized and subscribes only to its own data.

```typescript
// components/nodes/TaskNode.tsx
import { memo, useCallback, useRef, useEffect } from 'react'
import { Handle, Position } from 'reactflow'
import { useTask } from '../../selectors/taskSelectors'
import { useGraphStore } from '../../stores/graphStore'

interface TaskNodeProps {
  id: string
}

// This component ONLY re-renders when task data changes
export const TaskNode = memo(function TaskNode({ id }: TaskNodeProps) {
  const task = useTask(id)
  const updateDimensions = useGraphStore((state) => state.actions.updateTaskDimensions)
  const nodeRef = useRef<HTMLDivElement>(null)

  // Calculate and store dimensions when content changes
  useEffect(() => {
    if (!nodeRef.current) return

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (entry) {
        updateDimensions(id, {
          width: entry.contentRect.width,
          height: entry.contentRect.height,
          calculatedAt: Date.now(),
        })
      }
    })

    observer.observe(nodeRef.current)
    return () => observer.disconnect()
  }, [id, updateDimensions])

  if (!task) return null

  return (
    <div
      ref={nodeRef}
      className={`task-node task-node--${task.status}`}
    >
      <Handle type="target" position={Position.Left} />

      <div className="task-node__header">
        <span className="task-node__type-badge">{task.type}</span>
        <span className="task-node__status">{task.status}</span>
      </div>

      <div className="task-node__name">{task.name}</div>

      <Handle type="source" position={Position.Right} />
    </div>
  )
}, (prevProps, nextProps) => {
  // Custom comparison - only re-render if ID changes
  // (task data changes are handled by selector subscription)
  return prevProps.id === nextProps.id
})
```

### Container Node with Pagination

```typescript
// components/nodes/SwarmNode.tsx
import { memo, useCallback, useState } from 'react'
import { useTask, useVisibleSubtasks, useSubtaskPagination } from '../../selectors/taskSelectors'
import { useProgressiveLoader } from '../../hooks/useProgressiveLoader'
import { TaskNode } from './TaskNode'

interface SwarmNodeProps {
  id: string
}

export const SwarmNode = memo(function SwarmNode({ id }: SwarmNodeProps) {
  const task = useTask(id)
  const pagination = useSubtaskPagination(id)
  const visibleSubtasks = useVisibleSubtasks(id)
  const { loadSubtasks } = useProgressiveLoader(null)

  const [isExpanded, setIsExpanded] = useState(false)

  // Load first page when expanded
  const handleExpand = useCallback(async () => {
    if (!isExpanded && task?.subtasksLoadingState === 'idle') {
      await loadSubtasks(id, 0)
    }
    setIsExpanded(!isExpanded)
  }, [isExpanded, id, task?.subtasksLoadingState, loadSubtasks])

  // Pagination handlers
  const handleNextPage = useCallback(async () => {
    if (!pagination) return
    const nextPage = pagination.currentPage + 1
    await loadSubtasks(id, nextPage)
  }, [id, pagination, loadSubtasks])

  const handlePrevPage = useCallback(async () => {
    if (!pagination || pagination.currentPage === 0) return
    const prevPage = pagination.currentPage - 1
    // Previous page should already be loaded, just update current page
    useGraphStore.getState().actions.setSubtaskPage(id, prevPage)
  }, [id, pagination])

  if (!task) return null

  return (
    <div className="swarm-node">
      <div className="swarm-node__header" onClick={handleExpand}>
        <span className="swarm-node__name">{task.name}</span>
        <span className="swarm-node__count">
          {task.subtaskIds.length} tasks
        </span>
        <button className="swarm-node__expand-btn">
          {isExpanded ? '−' : '+'}
        </button>
      </div>

      {isExpanded && (
        <div className="swarm-node__children">
          {task.subtasksLoadingState === 'loading' ? (
            <div className="swarm-node__loading">Loading...</div>
          ) : (
            <>
              <div className="swarm-node__tasks">
                {visibleSubtasks.map(subtask => (
                  <TaskNodeWrapper
                    key={subtask.id}
                    id={subtask.id}
                  />
                ))}
              </div>

              {pagination && pagination.totalCount > pagination.pageSize && (
                <div className="swarm-node__pagination">
                  <button
                    onClick={handlePrevPage}
                    disabled={pagination.currentPage === 0}
                  >
                    Previous
                  </button>
                  <span>
                    Page {pagination.currentPage + 1} of{' '}
                    {Math.ceil(pagination.totalCount / pagination.pageSize)}
                  </span>
                  <button
                    onClick={handleNextPage}
                    disabled={
                      (pagination.currentPage + 1) * pagination.pageSize >=
                      pagination.totalCount
                    }
                  >
                    Next
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
})

// Wrapper that handles node type routing
const TaskNodeWrapper = memo(function TaskNodeWrapper({ id }: { id: string }) {
  const task = useTask(id)

  if (!task) return null

  switch (task.type) {
    case 'swarm':
      return <SwarmNode id={id} />
    case 'chain':
      return <ChainNode id={id} />
    default:
      return <TaskNode id={id} />
  }
})
```

---

## 5. Dimension Calculation System

Each node calculates and reports its own dimensions. The layout engine uses these for positioning.

```typescript
// hooks/useDimensionCalculator.ts
import { useEffect, useRef, useCallback } from 'react'
import { useGraphStore } from '../stores/graphStore'

export function useDimensionCalculator(taskId: string) {
  const nodeRef = useRef<HTMLDivElement>(null)
  const updateDimensions = useGraphStore(
    (state) => state.actions.updateTaskDimensions
  )

  // Debounced dimension update
  const updateDimensionsDebounced = useCallback(() => {
    if (!nodeRef.current) return

    const rect = nodeRef.current.getBoundingClientRect()
    updateDimensions(taskId, {
      width: rect.width,
      height: rect.height,
      calculatedAt: Date.now(),
    })
  }, [taskId, updateDimensions])

  useEffect(() => {
    if (!nodeRef.current) return

    // Initial calculation
    updateDimensionsDebounced()

    // Watch for size changes
    const observer = new ResizeObserver(() => {
      updateDimensionsDebounced()
    })

    observer.observe(nodeRef.current)
    return () => observer.disconnect()
  }, [updateDimensionsDebounced])

  return nodeRef
}
```

### Layout Engine Integration

```typescript
// layout/layoutEngine.ts
import dagre from 'dagre'
import { Task, Edge } from '../types'

interface LayoutOptions {
  direction: 'LR' | 'TB'
  nodeSpacing: number
  rankSpacing: number
}

export function calculateLayout(
  tasks: Record<string, Task>,
  edges: Edge[],
  rootId: string,
  options: LayoutOptions
): Map<string, { x: number; y: number }> {
  const g = new dagre.graphlib.Graph({ compound: true })

  g.setGraph({
    rankdir: options.direction,
    nodesep: options.nodeSpacing,
    ranksep: options.rankSpacing,
  })
  g.setDefaultEdgeLabel(() => ({}))

  // Add nodes with their calculated dimensions
  const relevantTaskIds = getRelevantTaskIds(tasks, edges, rootId)

  for (const taskId of relevantTaskIds) {
    const task = tasks[taskId]
    if (!task) continue

    // Use calculated dimensions or defaults
    const width = task.dimensions?.width ?? 150
    const height = task.dimensions?.height ?? 50

    g.setNode(taskId, { width, height })

    // Set parent for compound nodes (swarm/chain children)
    if (task.parentId && relevantTaskIds.has(task.parentId)) {
      g.setParent(taskId, task.parentId)
    }
  }

  // Add edges
  for (const edge of edges) {
    if (relevantTaskIds.has(edge.source) && relevantTaskIds.has(edge.target)) {
      g.setEdge(edge.source, edge.target)
    }
  }

  // Run layout
  dagre.layout(g)

  // Extract positions
  const positions = new Map<string, { x: number; y: number }>()
  g.nodes().forEach(nodeId => {
    const node = g.node(nodeId)
    if (node) {
      positions.set(nodeId, { x: node.x, y: node.y })
    }
  })

  return positions
}

function getRelevantTaskIds(
  tasks: Record<string, Task>,
  edges: Edge[],
  rootId: string
): Set<string> {
  const ids = new Set<string>()
  const queue = [rootId]

  while (queue.length > 0) {
    const id = queue.shift()!
    if (ids.has(id)) continue
    ids.add(id)

    const task = tasks[id]
    if (!task) continue

    // Add subtasks
    task.subtaskIds.forEach(subId => queue.push(subId))

    // Add callbacks
    task.successCallbackIds.forEach(cbId => queue.push(cbId))
    task.errorCallbackIds.forEach(cbId => queue.push(cbId))
  }

  return ids
}
```

---

## 6. API Layer

### API Client with Batching and Caching

```typescript
// api/client.ts
import { Task } from '../types'

const API_BASE = '/api/v1'
const BATCH_SIZE = 50
const CACHE_TTL = 30000 // 30 seconds

class APIClient {
  private cache = new Map<string, { data: any; timestamp: number }>()
  private pendingBatches = new Map<string, Promise<Task[]>>()

  // Cached fetch with TTL
  private async cachedFetch<T>(key: string, fetcher: () => Promise<T>): Promise<T> {
    const cached = this.cache.get(key)
    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
      return cached.data
    }

    const data = await fetcher()
    this.cache.set(key, { data, timestamp: Date.now() })
    return data
  }

  // Get root task IDs
  async getRootTaskIds(): Promise<string[]> {
    return this.cachedFetch('roots', async () => {
      const response = await fetch(`${API_BASE}/workflows/roots`)
      const data = await response.json()
      return data.taskIds
    })
  }

  // Batch fetch tasks - automatically batches concurrent requests
  async getTasksBatch(taskIds: string[]): Promise<Task[]> {
    if (taskIds.length === 0) return []

    // Check cache first
    const uncachedIds: string[] = []
    const cachedTasks: Task[] = []

    for (const id of taskIds) {
      const cached = this.cache.get(`task:${id}`)
      if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
        cachedTasks.push(cached.data)
      } else {
        uncachedIds.push(id)
      }
    }

    if (uncachedIds.length === 0) {
      return cachedTasks
    }

    // Batch uncached requests
    const batches: string[][] = []
    for (let i = 0; i < uncachedIds.length; i += BATCH_SIZE) {
      batches.push(uncachedIds.slice(i, i + BATCH_SIZE))
    }

    const batchResults = await Promise.all(
      batches.map(batch => this.fetchTaskBatch(batch))
    )

    const fetchedTasks = batchResults.flat()

    // Cache fetched tasks
    fetchedTasks.forEach(task => {
      this.cache.set(`task:${task.id}`, { data: task, timestamp: Date.now() })
    })

    return [...cachedTasks, ...fetchedTasks]
  }

  private async fetchTaskBatch(taskIds: string[]): Promise<Task[]> {
    const response = await fetch(`${API_BASE}/tasks/batch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ taskIds }),
    })
    return response.json()
  }

  // Get paginated subtasks
  async getTaskSubtasks(
    taskId: string,
    options: { page: number; pageSize: number }
  ): Promise<{ taskIds: string[]; totalCount: number }> {
    const { page, pageSize } = options
    const response = await fetch(
      `${API_BASE}/tasks/${taskId}/subtasks?page=${page}&pageSize=${pageSize}`
    )
    return response.json()
  }

  // Invalidate cache for a task (used when receiving updates)
  invalidateTask(taskId: string) {
    this.cache.delete(`task:${taskId}`)
  }
}

export const api = new APIClient()
```

---

## 7. Real-time Updates via WebSocket

```typescript
// hooks/useRealtimeUpdates.ts
import { useEffect, useRef } from 'react'
import { useGraphStore } from '../stores/graphStore'
import { api } from '../api/client'

export function useRealtimeUpdates() {
  const wsRef = useRef<WebSocket | null>(null)
  const actions = useGraphStore((state) => state.actions)
  const tasks = useGraphStore((state) => state.tasks)

  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws/tasks')
    wsRef.current = ws

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data)

      switch (message.type) {
        case 'task_status_changed':
          // Only update if we have this task loaded
          if (tasks[message.taskId]) {
            actions.updateTaskStatus(message.taskId, message.status)
          }
          break

        case 'task_updated':
          // Invalidate cache and refetch if loaded
          api.invalidateTask(message.taskId)
          if (tasks[message.taskId]) {
            api.getTasksBatch([message.taskId]).then(([task]) => {
              if (task) actions.setTask(task)
            })
          }
          break

        case 'subtask_added':
          // If parent is loaded and expanded, add the new subtask
          const parent = tasks[message.parentId]
          if (parent) {
            actions.appendSubtaskIds(
              message.parentId,
              [message.taskId],
              parent.subtasksPagination.currentPage
            )
          }
          break
      }
    }

    return () => {
      ws.close()
    }
  }, [actions, tasks])
}
```

---

## 8. Performance Optimizations Summary

### 1. Avoid Full Graph Re-renders

```typescript
// BAD - Re-renders entire graph on any change
function Graph() {
  const tasks = useGraphStore(state => state.tasks) // Subscribes to ALL tasks
  return tasks.map(t => <Node task={t} />)
}

// GOOD - Each node subscribes to its own data
function Graph() {
  const taskIds = useGraphStore(state => Object.keys(state.tasks))
  return taskIds.map(id => <Node key={id} id={id} />) // Node fetches its own data
}

function Node({ id }) {
  const task = useTask(id) // Only re-renders when THIS task changes
  return <div>{task.name}</div>
}
```

### 2. Batch API Requests

```typescript
// BAD - N requests for N tasks
for (const id of taskIds) {
  const task = await api.getTask(id)
}

// GOOD - 1 request for N tasks
const tasks = await api.getTasksBatch(taskIds)
```

### 3. Lazy Load Subtasks

```typescript
// BAD - Load all subtasks immediately
useEffect(() => {
  loadAllSubtasks(taskId)
}, [taskId])

// GOOD - Load on expand, paginate
const handleExpand = () => {
  if (!isExpanded) {
    loadSubtasks(taskId, page: 0, pageSize: 20)
  }
  setIsExpanded(!isExpanded)
}
```

### 4. Memoize Expensive Calculations

```typescript
// BAD - Recalculate layout on every render
function Graph() {
  const layout = calculateLayout(tasks, edges) // Expensive!
  return <Canvas layout={layout} />
}

// GOOD - Only recalculate when dependencies change
function Graph() {
  const layout = useMemo(
    () => calculateLayout(tasks, edges),
    [taskIds, edgeIds] // Only IDs, not full objects
  )
  return <Canvas layout={layout} />
}
```

### 5. Virtual Scrolling for Large Lists

```typescript
// For swarms with 1000s of tasks, virtualize the list
import { FixedSizeList } from 'react-window'

function SwarmChildren({ subtaskIds }) {
  return (
    <FixedSizeList
      height={400}
      itemCount={subtaskIds.length}
      itemSize={50}
    >
      {({ index, style }) => (
        <div style={style}>
          <TaskNode id={subtaskIds[index]} />
        </div>
      )}
    </FixedSizeList>
  )
}
```

---

## 9. File Structure

```
src/
├── api/
│   ├── client.ts           # API client with batching/caching
│   └── types.ts            # API response types
│
├── stores/
│   ├── graphStore.ts       # Main Zustand store
│   └── middleware/
│       └── immer.ts        # Immer middleware for immutable updates
│
├── selectors/
│   ├── taskSelectors.ts    # Task-related selectors
│   ├── edgeSelectors.ts    # Edge-related selectors
│   └── uiSelectors.ts      # UI state selectors
│
├── hooks/
│   ├── useProgressiveLoader.ts  # Progressive loading logic
│   ├── useRealtimeUpdates.ts    # WebSocket subscription
│   ├── useDimensionCalculator.ts # Node dimension tracking
│   └── useLayout.ts             # Layout calculation hook
│
├── components/
│   ├── WorkflowViewer.tsx       # Main container
│   ├── WorkflowTabs.tsx         # Root task tabs
│   ├── GraphCanvas.tsx          # React Flow canvas
│   ├── TaskInfoPanel.tsx        # Selected task details
│   │
│   └── nodes/
│       ├── TaskNode.tsx         # Basic task node
│       ├── SwarmNode.tsx        # Swarm container node
│       ├── ChainNode.tsx        # Chain container node
│       ├── BatchItemNode.tsx    # Batch item wrapper
│       └── PaginationControls.tsx
│
├── layout/
│   ├── layoutEngine.ts          # Dagre layout wrapper
│   └── positionCalculator.ts    # Position calculation utilities
│
├── types/
│   ├── task.ts                  # Task type definitions
│   ├── edge.ts                  # Edge type definitions
│   └── ui.ts                    # UI state types
│
└── utils/
    ├── memoize.ts               # Memoization utilities
    └── batchQueue.ts            # Request batching queue
```

---

## 10. Server API Endpoints (Python/FastAPI)

Add these endpoints to support the React client:

```python
# api/routes/tasks.py
from fastapi import APIRouter, Query
from typing import List
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1")

class PaginatedResponse(BaseModel):
    task_ids: List[str]
    total_count: int
    page: int
    page_size: int

@router.get("/workflows/roots")
async def get_root_tasks():
    """Return IDs of root tasks (tasks not called by any other task)"""
    tasks = await extract_signatures()
    ctx = create_builders(tasks)
    root_ids = find_unmentioned_tasks(ctx)
    return {"taskIds": root_ids}

@router.post("/tasks/batch")
async def get_tasks_batch(request: dict):
    """Batch fetch multiple tasks by ID"""
    task_ids = request.get("taskIds", [])
    tasks = await get_tasks_by_ids(task_ids)
    return [serialize_task(t) for t in tasks]

@router.get("/tasks/{task_id}/subtasks")
async def get_task_subtasks(
    task_id: str,
    page: int = Query(0, ge=0),
    page_size: int = Query(20, ge=1, le=100)
):
    """Get paginated subtasks for a swarm or chain"""
    task = await rapyer.aget(task_id)

    if isinstance(task, (SwarmTaskSignature, ChainTaskSignature)):
        all_subtask_ids = list(task.tasks)
        start = page * page_size
        end = start + page_size
        page_ids = all_subtask_ids[start:end]

        return PaginatedResponse(
            task_ids=page_ids,
            total_count=len(all_subtask_ids),
            page=page,
            page_size=page_size
        )

    return PaginatedResponse(
        task_ids=[],
        total_count=0,
        page=page,
        page_size=page_size
    )
```

---

## Summary

This architecture provides:

1. **Progressive Loading**: Root → Callbacks → Subtasks in layers
2. **Pagination**: Never load all subtasks at once
3. **Normalized State**: Flat structure for O(1) updates
4. **Selective Re-rendering**: Components only update when their data changes
5. **Dimension Calculation**: Each node reports its own size
6. **Batched API Calls**: Reduce network overhead
7. **Real-time Updates**: WebSocket for live status changes
8. **Virtualization Ready**: Can handle 1000s of nodes with react-window

The key insight is separating **data identity** (task IDs) from **data content** (task objects). Components subscribe to specific IDs, and the store handles updates efficiently through normalization.
