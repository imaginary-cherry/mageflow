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
    expect(task!.metadata).toHaveProperty('param1')
    expect(task!.metadata).toHaveProperty('param2')
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

    result.tasks.forEach(task => {
      expect(typeof task.id).toBe('string')
      expect(typeof task.name).toBe('string')
      expect(typeof task.status).toBe('string')
      expect(['pending', 'running', 'completed', 'failed', 'cancelled', 'paused']).toContain(task.status)
    })
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
