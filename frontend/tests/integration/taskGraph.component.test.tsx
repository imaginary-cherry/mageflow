import { describe, it, expect, inject, beforeEach, afterEach, vi } from 'vitest'
import { mockIPC, clearMocks } from '@tauri-apps/api/mocks'
import { render, screen, waitFor, cleanup } from '@testing-library/react'
import App from '@/App'
import { seedTestData, cleanupTestData, mageVoyanceRoot } from './setup/seedManager'

// jsdom doesn't provide window.matchMedia — needed by Sonner toast component
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

// jsdom doesn't provide ResizeObserver — needed by @xyflow/react
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver

// jsdom doesn't provide DOMMatrixReadOnly — needed by @xyflow/react node positioning
class DOMMatrixReadOnlyStub {
  m22: number
  constructor(init?: string | number[]) {
    const values = typeof init === 'string' ? [] : (init ?? [1, 0, 0, 1, 0, 0])
    this.m22 = values[3] ?? 1
  }
  transformPoint() { return { x: 0, y: 0 } }
}
// @ts-expect-error - stub for jsdom
globalThis.DOMMatrixReadOnly = DOMMatrixReadOnlyStub

declare module 'vitest' {
  export interface ProvidedContext {
    serverUrl: string
    authServerUrl: string
    ipcToken: string
  }
}

function setupTauriMocks(port: number, ipcToken?: string) {
  mockIPC((cmd) => {
    switch (cmd) {
      case 'load_all_secrets':
        return JSON.stringify({ hatchetApiKey: 'fake-key', redisUrl: 'redis://fake' })
      case 'get_sidecar_port':
        return port
      case 'get_ipc_token':
        return ipcToken ?? ''
      case 'set_tray_status':
        return undefined
      default:
        return undefined
    }
  }, { shouldMockEvents: true })
}

describe('TaskGraph with IPC auth integration', () => {
  beforeEach(async () => {
    await seedTestData(mageVoyanceRoot)
  })

  afterEach(async () => {
    // cleanup() must run BEFORE clearMocks() so React unmount effects
    // (which call Tauri unlisten functions) execute while mocks are still active.
    cleanup()
    clearMocks()
    await cleanupTestData(mageVoyanceRoot)
  })

  it('renders task nodes when IPC token is valid', async () => {
    const authServerUrl = inject('authServerUrl')
    const ipcToken = inject('ipcToken')
    const port = Number(new URL(authServerUrl).port)
    setupTauriMocks(port, ipcToken)

    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('basic_test_task')).toBeInTheDocument()
    }, { timeout: 20000 })

    expect(screen.getByText(/test_chain/)).toBeInTheDocument()
    expect(screen.getByText(/test_swarm/)).toBeInTheDocument()
    expect(screen.getByText('task_with_callbacks')).toBeInTheDocument()
  })

  it('does not render task nodes when IPC token is missing', async () => {
    const authServerUrl = inject('authServerUrl')
    const port = Number(new URL(authServerUrl).port)
    setupTauriMocks(port, '')

    render(<App />)

    // Wait for the app to reach ready state
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /open settings/i })).toBeInTheDocument()
    }, { timeout: 20000 })

    // Task names from seed data should NOT be rendered
    expect(screen.queryByText('basic_test_task')).not.toBeInTheDocument()
    expect(screen.queryByText(/test_chain/)).not.toBeInTheDocument()
    expect(screen.queryByText(/test_swarm/)).not.toBeInTheDocument()

    // Let the rejected 403 promise settle before teardown so it's caught
    // by the store's try/catch rather than surfacing as an unhandled rejection.
    await new Promise(resolve => setTimeout(resolve, 100))
  })
})
