import { describe, it, expect, inject, beforeEach, afterEach, vi } from 'vitest'
import { mockIPC, clearMocks } from '@tauri-apps/api/mocks'
import { render, screen, waitFor, cleanup } from '@testing-library/react'
import App from '@/App'
import { validateCredentials } from '@/stores/settingsStore'

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

declare module 'vitest' {
  export interface ProvidedContext {
    serverUrl: string
  }
}

function setupTauriMocks(port: number) {
  mockIPC((cmd, payload) => {
    switch (cmd) {
      case 'load_secret': {
        const key = (payload as Record<string, unknown>).key
        if (key === 'hatchetApiKey') return 'fake-key'
        if (key === 'redisUrl') return 'redis://fake'
        return null
      }
      case 'get_sidecar_port':
        return port
      case 'set_tray_status':
        return undefined
      case 'check_keychain_health':
        return 'ok'
      default:
        return undefined
    }
  }, { shouldMockEvents: true })
}

describe('Health endpoint component integration', () => {
  let port: number

  beforeEach(() => {
    const serverUrl = inject('serverUrl')
    port = Number(new URL(serverUrl).port)
    setupTauriMocks(port)
  })

  afterEach(() => {
    clearMocks()
    cleanup()
  })

  it('app transitions to ready with real health endpoint', async () => {
    render(<App />)

    // App should eventually reach ready phase and render the main UI
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /open settings/i })).toBeInTheDocument()
    }, { timeout: 20000 })
  })

  it('validateCredentials returns valid against real backend', async () => {
    // Mock invoke so validate_credentials throws (forcing health polling fallback)
    // and restart_sidecar returns the real port
    mockIPC((cmd) => {
      switch (cmd) {
        case 'validate_credentials':
          throw new Error('command not available')
        case 'restart_sidecar':
          return port
        case 'load_secret':
          return null
        case 'save_secret':
          return undefined
        case 'set_tray_status':
          return undefined
        default:
          return undefined
      }
    }, { shouldMockEvents: true })

    const result = await validateCredentials({
      hatchetApiKey: 'fake-key',
      redisUrl: 'redis://fake',
    })

    expect(result.valid).toBe(true)
    expect(result.hatchetError).toBeUndefined()
    expect(result.redisError).toBeUndefined()
  })
})
