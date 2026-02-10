import { describe, it, expect, inject, beforeAll, afterAll } from 'vitest'
import { HttpTaskClient } from '@/services/httpTaskClient'
import type { TaskClient } from '@/services/types'
import { seedTestData, cleanupTestData, projectRoot } from './setup/seedManager'

declare module 'vitest' {
  export interface ProvidedContext {
    serverUrl: string
  }
}

describe('TaskClient integration', () => {
  let client: TaskClient

  beforeAll(async () => {
    const serverUrl = inject('serverUrl')
    client = new HttpTaskClient(serverUrl)
    await seedTestData(projectRoot)
  })

  afterAll(async () => {
    await cleanupTestData(projectRoot)
  })

  it('getRootTaskIds returns seeded root tasks', async () => {
    // Arrange
    const expectedRootIds = [
      'ChainTaskSignature:test_frontend_chain_001',
      'SwarmTaskSignature:test_frontend_swarm_001',
      'TaskSignature:test_frontend_task_with_callbacks_001',
      'TaskSignature:test_frontend_basic_task_001',
    ]

    // Act
    const rootIds = await client.getRootTaskIds()

    // Assert
    expect(rootIds).toBeInstanceOf(Array)
    expect(rootIds.length).toBeGreaterThan(0)
    rootIds.forEach(id => expect(typeof id).toBe('string'))
    expectedRootIds.forEach(expectedId => {
      expect(rootIds).toContain(expectedId)
    })
  })

  it('getTask returns a valid task with correct field shapes and values', async () => {
    // Arrange
    const taskId = 'TaskSignature:test_frontend_basic_task_001'

    // Act
    const task = await client.getTask(taskId)

    // Assert
    expect(task).toBeDefined()
    expect(typeof task!.id).toBe('string')
    expect(typeof task!.name).toBe('string')
    expect(typeof task!.status).toBe('string')
    expect(Array.isArray(task!.children_ids)).toBe(true)
    expect(typeof task!.metadata).toBe('object')

    expect(task!.id).toBe(taskId)
    expect(task!.name).toBe('basic_test_task')
    expect(task!.status).toBe('pending')
    expect(task!.type).toBe('simple')
    expect(task!.metadata?.param1).toBe('value1')
    expect(task!.metadata?.param2).toBe(42)
    expect(task!.children_ids).toEqual([])
    expect(task!.success_callback_ids).toEqual([])
    expect(task!.error_callback_ids).toEqual([])
  })

  it('getTask returns undefined for nonexistent task', async () => {
    // Arrange
    const nonexistentId = 'nonexistent_task_id'

    // Act
    const task = await client.getTask(nonexistentId)

    // Assert
    expect(task).toBeUndefined()
  })

  it('getTask returns chain task with correct type and children', async () => {
    // Arrange
    const chainId = 'ChainTaskSignature:test_frontend_chain_001'
    const expectedChildren = [
      'TaskSignature:test_frontend_chain_task_001',
      'TaskSignature:test_frontend_chain_task_002',
    ]

    // Act
    const task = await client.getTask(chainId)

    // Assert
    expect(task).toBeDefined()
    expect(task!.type).toBe('chain')
    expect(['simple', 'chain', 'swarm']).toContain(task!.type)
    expect(task!.name).toBe('test_chain')
    expect(task!.status).toBe('running')
    expect(task!.metadata).toEqual({ chain_param: 'chain_value' })
    expect(task!.children_ids.length).toBe(2)
    expectedChildren.forEach(childId => {
      expect(task!.children_ids).toContain(childId)
    })
  })

  it('getChildren returns paginated children for chain', async () => {
    // Arrange
    const chainId = 'ChainTaskSignature:test_frontend_chain_001'
    const page = 1
    const limit = 10

    // Act
    const result = await client.getChildren(chainId, page, limit)

    // Assert
    expect(result).toHaveProperty('tasks')
    expect(result).toHaveProperty('total')
    expect(result).toHaveProperty('page')
    expect(Array.isArray(result.tasks)).toBe(true)
    expect(typeof result.total).toBe('number')
    expect(typeof result.page).toBe('number')

    expect(result.tasks.length).toBeGreaterThan(0)
    expect(result.total).toBe(2)
    expect(result.page).toBe(page)

    const child1 = result.tasks.find(t => t.id === 'TaskSignature:test_frontend_chain_task_001')
    expect(child1).toBeDefined()
    expect(child1!.name).toBe('chain_step_1')
    expect(child1!.status).toBe('pending')
    expect(child1!.metadata?.step).toBe(1)

    const child2 = result.tasks.find(t => t.id === 'TaskSignature:test_frontend_chain_task_002')
    expect(child2).toBeDefined()
    expect(child2!.name).toBe('chain_step_2')
    expect(child2!.status).toBe('pending')
    expect(child2!.metadata?.step).toBe(2)
  })

  it('getChildren returns paginated children for swarm', async () => {
    // Arrange
    const swarmId = 'SwarmTaskSignature:test_frontend_swarm_001'
    const page = 1
    const limit = 10

    // Act
    const result = await client.getChildren(swarmId, page, limit)

    // Assert
    expect(result).toHaveProperty('tasks')
    expect(result).toHaveProperty('total')
    expect(result).toHaveProperty('page')

    expect(result.tasks.length).toBe(3)
    expect(result.total).toBe(3)

    result.tasks.forEach(task => {
      expect(task.name).toBe('swarm_item_task')
      expect(task.status).toBe('pending')
    })

    const child0 = result.tasks.find(t => t.id === 'TaskSignature:test_frontend_swarm_original_000')
    expect(child0).toBeDefined()
    expect(child0!.metadata?.item_index).toBe(0)

    const child1 = result.tasks.find(t => t.id === 'TaskSignature:test_frontend_swarm_original_001')
    expect(child1).toBeDefined()
    expect(child1!.metadata?.item_index).toBe(1)

    const child2 = result.tasks.find(t => t.id === 'TaskSignature:test_frontend_swarm_original_002')
    expect(child2).toBeDefined()
    expect(child2!.metadata?.item_index).toBe(2)
  })

  it('getTask returns swarm task with correct values', async () => {
    // Arrange
    const taskId = 'SwarmTaskSignature:test_frontend_swarm_001'

    // Act
    const task = await client.getTask(taskId)

    // Assert
    expect(task).toBeDefined()
    expect(task!.id).toBe(taskId)
    expect(task!.name).toBe('test_swarm')
    expect(task!.type).toBe('swarm')
    expect(task!.status).toBe('running')
    expect(task!.metadata).toEqual({ swarm_param: 'swarm_value' })
    expect(task!.children_ids.length).toBe(3)
    expect(task!.children_ids).toContain('TaskSignature:test_frontend_swarm_original_000')
    expect(task!.children_ids).toContain('TaskSignature:test_frontend_swarm_original_001')
    expect(task!.children_ids).toContain('TaskSignature:test_frontend_swarm_original_002')
  })

  it('getTask returns task_with_callbacks with callback IDs', async () => {
    // Arrange
    const taskId = 'TaskSignature:test_frontend_task_with_callbacks_001'

    // Act
    const task = await client.getTask(taskId)

    // Assert
    expect(task).toBeDefined()
    expect(task!.id).toBe(taskId)
    expect(task!.name).toBe('task_with_callbacks')
    expect(task!.type).toBe('simple')
    expect(task!.status).toBe('running')
    expect(task!.metadata).toEqual({ has_callbacks: true })
    expect(task!.success_callback_ids).toContain('TaskSignature:test_frontend_success_callback_001')
    expect(task!.success_callback_ids.length).toBe(1)
    expect(task!.error_callback_ids).toContain('TaskSignature:test_frontend_error_callback_001')
    expect(task!.error_callback_ids.length).toBe(1)
  })

  it('getTask returns callback tasks individually', async () => {
    // Arrange
    const successId = 'TaskSignature:test_frontend_success_callback_001'
    const errorId = 'TaskSignature:test_frontend_error_callback_001'

    // Act
    const successTask = await client.getTask(successId)
    const errorTask = await client.getTask(errorId)

    // Assert
    expect(successTask).toBeDefined()
    expect(successTask!.name).toBe('on_success_callback')
    expect(successTask!.status).toBe('pending')
    expect(successTask!.metadata?.callback_type).toBe('success')

    expect(errorTask).toBeDefined()
    expect(errorTask!.name).toBe('on_error_callback')
    expect(errorTask!.status).toBe('pending')
    expect(errorTask!.metadata?.callback_type).toBe('error')
  })

  it('cancelTask throws for nonexistent task', async () => {
    // Arrange
    const nonexistentId = 'nonexistent_task'

    // Act & Assert
    await expect(client.cancelTask(nonexistentId)).rejects.toThrow()
  })

  it('pauseTask throws for nonexistent task', async () => {
    // Arrange
    const nonexistentId = 'nonexistent_task'

    // Act & Assert
    await expect(client.pauseTask(nonexistentId)).rejects.toThrow()
  })

  it('retryTask throws for nonexistent task', async () => {
    // Arrange
    const nonexistentId = 'nonexistent_task'

    // Act & Assert
    await expect(client.retryTask(nonexistentId)).rejects.toThrow()
  })
})
