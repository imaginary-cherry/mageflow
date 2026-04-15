import { mockIPC } from '@tauri-apps/api/mocks';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

type IpcOverrides = Partial<Record<string, unknown | ((...args: unknown[]) => unknown)>>;

const IPC_DEFAULTS: Record<string, unknown> = {
  load_all_secrets: null,
  save_secret: undefined,
  get_sidecar_port: 8089,
  restart_sidecar: 8089,
  get_ipc_token: 'test-ipc-token',
  set_tray_status: undefined,
};

/**
 * Sets up Tauri IPC mocking with sensible defaults.
 * Pass overrides to customize specific command responses.
 * Override values can be raw values or functions.
 */
export function mockTauriIPC(overrides?: IpcOverrides): void {
  const merged = { ...IPC_DEFAULTS, ...overrides };

  mockIPC((cmd: string, payload?: Record<string, unknown>) => {
    // Strip the plugin:xxx| prefix if present
    const command = cmd.includes('|') ? cmd.split('|')[1] : cmd;

    if (command in merged) {
      const val = merged[command];
      if (typeof val === 'function') {
        return (val as (payload?: Record<string, unknown>) => unknown)(payload);
      }
      return val;
    }
    return undefined;
  });
}

interface HealthStatus {
  status: string;
  hatchet: string;
  redis: string;
}

const DEFAULT_HEALTH: HealthStatus = {
  status: 'ok',
  hatchet: 'connected',
  redis: 'connected',
};

/**
 * Creates an MSW server configured with a health endpoint handler.
 * Caller is responsible for calling .listen(), .resetHandlers(), and .close().
 */
export function createHealthServer(
  status?: Partial<HealthStatus>,
): ReturnType<typeof setupServer> {
  const healthResponse: HealthStatus = { ...DEFAULT_HEALTH, ...status };

  return setupServer(
    http.get('http://127.0.0.1:*/api/health', () => {
      return HttpResponse.json(healthResponse);
    }),
  );
}
