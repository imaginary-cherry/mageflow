import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { clearMocks } from '@tauri-apps/api/mocks';
import { mockTauriIPC } from '@/test/helpers';
import { useAppStartup } from '@/hooks/useAppStartup';

// Mock fetch globally to simulate health endpoint responses
function mockHealthFetch(response: { status?: string; hatchet?: string; redis?: string }) {
  const healthResponse = {
    status: response.status ?? 'ok',
    hatchet: response.hatchet ?? 'connected',
    redis: response.redis ?? 'connected',
  };

  vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(healthResponse),
  } as Response);
}

// Polling tests need generous timeouts
const TEST_TIMEOUT = 35000;

describe('useAppStartup', () => {
  afterEach(() => {
    clearMocks();
    vi.restoreAllMocks();
  });

  describe('phase transitions', () => {
    it('starts in loading-settings phase', () => {
      mockTauriIPC();

      const { result } = renderHook(() => useAppStartup());
      expect(result.current.phase).toBe('loading-settings');
    });

    it('transitions to onboarding when no settings found (TEST-02)', async () => {
      mockTauriIPC({ load_all_secrets: null });

      const { result } = renderHook(() => useAppStartup());

      await waitFor(() => {
        expect(result.current.phase).toBe('onboarding');
      }, { timeout: TEST_TIMEOUT });
    }, TEST_TIMEOUT);

    it('transitions to ready after full health check passes (TEST-01)', async () => {
      mockHealthFetch({ status: 'ok', hatchet: 'connected', redis: 'connected' });

      mockTauriIPC({
        load_all_secrets: JSON.stringify({
          hatchetApiKey: 'valid-key',
          redisUrl: 'redis://localhost:6379',
        }),
      });

      const { result } = renderHook(() => useAppStartup());

      await waitFor(() => {
        expect(result.current.phase).toBe('ready');
      }, { timeout: TEST_TIMEOUT });

      expect(result.current.port).toBe(8089);
      expect(result.current.ipcToken).toBe('test-ipc-token');
    }, TEST_TIMEOUT);

    it('transitions to startup-error with actionable message on hatchet failure', async () => {
      mockHealthFetch({ status: 'error', hatchet: 'disconnected', redis: 'connected' });

      mockTauriIPC({
        load_all_secrets: JSON.stringify({
          hatchetApiKey: 'bad-key',
          redisUrl: 'redis://localhost:6379',
        }),
      });

      const { result } = renderHook(() => useAppStartup());

      await waitFor(() => {
        expect(result.current.phase).toBe('startup-error');
      }, { timeout: TEST_TIMEOUT });

      expect(result.current.errorMessage).toContain('Hatchet');
      expect(result.current.errorMessage).toContain('Settings');
    }, TEST_TIMEOUT);
  });

  describe('tray status updates', () => {
    it('calls set_tray_status with connected when ready', async () => {
      mockHealthFetch({ status: 'ok', hatchet: 'connected', redis: 'connected' });

      const trayStatuses: string[] = [];
      mockTauriIPC({
        load_all_secrets: JSON.stringify({
          hatchetApiKey: 'valid-key',
          redisUrl: 'redis://localhost:6379',
        }),
        set_tray_status: (payload?: Record<string, unknown>) => {
          if (payload?.status) trayStatuses.push(payload.status as string);
          return undefined;
        },
      });

      const { result } = renderHook(() => useAppStartup());

      await waitFor(() => {
        expect(result.current.phase).toBe('ready');
      }, { timeout: TEST_TIMEOUT });

      expect(trayStatuses).toContain('connected');
    }, TEST_TIMEOUT);
  });

  describe('callbacks', () => {
    it('goToOnboarding transitions to onboarding phase', async () => {
      mockHealthFetch({ status: 'ok', hatchet: 'connected', redis: 'connected' });

      mockTauriIPC({
        load_all_secrets: JSON.stringify({
          hatchetApiKey: 'valid-key',
          redisUrl: 'redis://localhost:6379',
        }),
      });

      const { result } = renderHook(() => useAppStartup());

      await waitFor(() => {
        expect(result.current.phase).toBe('ready');
      }, { timeout: TEST_TIMEOUT });

      act(() => {
        result.current.goToOnboarding();
      });

      expect(result.current.phase).toBe('onboarding');
    }, TEST_TIMEOUT);
  });

  describe('browser dev mode', () => {
    it('skips invoke calls when not in Tauri environment', async () => {
      // Ensure __TAURI_INTERNALS__ is fully removed (clearMocks only deletes properties, not the object)
      delete (window as Record<string, unknown>).__TAURI_INTERNALS__;

      localStorage.setItem('mageflow_settings', JSON.stringify({
        hatchetApiKey: 'dev-key',
        redisUrl: 'redis://localhost:6379',
      }));

      const { result } = renderHook(() => useAppStartup());

      await waitFor(() => {
        expect(result.current.phase).toBe('ready');
      }, { timeout: TEST_TIMEOUT });

      expect(result.current.port).toBe(8000);

      localStorage.removeItem('mageflow_settings');
    }, TEST_TIMEOUT);
  });
});
