import { useEffect, useState, useCallback } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { loadSettings, isTauriEnvironment } from '@/stores/settingsStore';

export type AppPhase =
  | 'loading-settings'
  | 'onboarding'
  | 'keychain-error'
  | 'starting-sidecar'
  | 'connecting-hatchet'
  | 'connecting-redis'
  | 'ready'
  | 'startup-error';

const PHASE_MESSAGES: Record<AppPhase, string> = {
  'loading-settings': 'Loading settings...',
  'onboarding': 'Loading settings...',
  'keychain-error': '',
  'starting-sidecar': 'Starting backend...',
  'connecting-hatchet': 'Connecting to Hatchet...',
  'connecting-redis': 'Connecting to Redis...',
  'ready': 'Ready',
  'startup-error': '',
};

const TRAY_STATUS_MAP: Record<AppPhase, string> = {
  'loading-settings': 'starting',
  'onboarding': 'starting',
  'keychain-error': 'disconnected',
  'starting-sidecar': 'starting',
  'connecting-hatchet': 'starting',
  'connecting-redis': 'starting',
  'ready': 'connected',
  'startup-error': 'disconnected',
};

async function updateTrayStatus(phase: AppPhase): Promise<void> {
  if (!isTauriEnvironment()) return;
  try {
    await invoke('set_tray_status', { status: TRAY_STATUS_MAP[phase] });
  } catch {
    // Tray update failure should not block startup
  }
}

export interface UseAppStartupResult {
  phase: AppPhase;
  port: number;
  statusMessage: string;
  errorMessage: string;
  onOnboardingComplete: () => Promise<void>;
  retrySidecar: () => Promise<void>;
  goToOnboarding: () => void;
}

export function useAppStartup(): UseAppStartupResult {
  const [phase, setPhase] = useState<AppPhase>('loading-settings');
  const [port, setPort] = useState<number>(0);
  const [statusMessage, setStatusMessage] = useState<string>(PHASE_MESSAGES['loading-settings']);
  const [errorMessage, setErrorMessage] = useState<string>('');

  const transitionTo = useCallback((newPhase: AppPhase, customMessage?: string) => {
    setPhase(newPhase);
    setStatusMessage(customMessage ?? PHASE_MESSAGES[newPhase]);
    void updateTrayStatus(newPhase);
  }, []);

  /**
   * Poll the sidecar port (up to 20 attempts, 500ms apart).
   * Returns the port number, or throws if all attempts fail.
   */
  async function waitForSidecarPort(): Promise<number> {
    for (let i = 0; i < 20; i++) {
      await new Promise(resolve => setTimeout(resolve, 500));
      try {
        const p = await invoke<number>('get_sidecar_port');
        if (p > 0) return p;
      } catch {
        // keep retrying
      }
    }
    throw new Error('Backend failed to start');
  }

  interface HealthStatus {
    status?: string;
    hatchet?: string;
    redis?: string;
    detail?: string;
  }

  /**
   * Poll /api/health until the given service field equals "connected".
   * Throws on timeout (15s per service).
   */
  async function pollHealth(
    healthUrl: string,
    field: keyof HealthStatus,
    timeoutMs = 15000,
  ): Promise<void> {
    const deadline = Date.now() + timeoutMs;
    let lastErr: Error | null = null;
    while (Date.now() < deadline) {
      await new Promise(resolve => setTimeout(resolve, 500));
      try {
        const resp = await fetch(healthUrl);
        if (resp.ok) {
          const data = (await resp.json()) as HealthStatus;
          // If the field is explicitly "connected" we're done.
          // If the overall status is "ok" and the field is missing we treat it as connected
          // (simple health endpoint without per-service fields).
          if (data[field] === 'connected') return;
          if (!data[field] && data.status === 'ok') return;
          // field present but not connected — keep polling
        }
      } catch (e) {
        lastErr = e as Error;
      }
    }
    throw new Error(lastErr ? lastErr.message : `Timeout waiting for ${field}`);
  }

  /**
   * Core startup polling: given a port, drive through hatchet -> redis -> ready phases.
   * Extracted so it can be reused after onboarding.
   */
  const pollForReady = useCallback(async (resolvedPort: number) => {
    const healthUrl = `http://127.0.0.1:${resolvedPort}/api/health`;

    transitionTo('connecting-hatchet');
    try {
      await pollHealth(healthUrl, 'hatchet');
    } catch {
      transitionTo('startup-error', 'Could not connect to Hatchet');
      setErrorMessage('Could not connect to Hatchet');
      return;
    }

    transitionTo('connecting-redis');
    try {
      await pollHealth(healthUrl, 'redis');
    } catch {
      transitionTo('startup-error', 'Could not connect to Redis');
      setErrorMessage('Could not connect to Redis');
      return;
    }

    transitionTo('ready');
  }, [transitionTo]);

  /**
   * Full startup sequence. Returns early after a phase error.
   */
  const runStartup = useCallback(async () => {
    transitionTo('loading-settings');

    const settings = await loadSettings();
    if (!settings) {
      // Distinguish "no credentials" from "keychain access denied"
      if (isTauriEnvironment()) {
        try {
          const health = await invoke<string>('check_keychain_health');
          if (health.startsWith('denied')) {
            transitionTo('keychain-error');
            setErrorMessage(health.slice('denied:'.length));
            return;
          }
        } catch {
          // Command unavailable — fall through to onboarding
        }
      }
      transitionTo('onboarding');
      return;
    }

    if (!isTauriEnvironment()) {
      // Browser dev mode — skip invoke calls, use VITE_API_URL or default port 8000
      const devPort = parseInt(import.meta.env.VITE_API_PORT ?? '8000', 10);
      setPort(devPort);
      transitionTo('ready');
      return;
    }

    transitionTo('starting-sidecar');
    let resolvedPort: number;
    try {
      resolvedPort = await waitForSidecarPort();
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Backend failed to start';
      transitionTo('startup-error', msg);
      setErrorMessage(msg);
      return;
    }
    setPort(resolvedPort);

    await pollForReady(resolvedPort);
  }, [transitionTo, pollForReady]);

  useEffect(() => {
    void runStartup();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onOnboardingComplete = useCallback(async () => {
    if (!isTauriEnvironment()) {
      const devPort = parseInt(import.meta.env.VITE_API_PORT ?? '8000', 10);
      setPort(devPort);
      transitionTo('ready');
      return;
    }

    transitionTo('starting-sidecar');

    let resolvedPort: number;
    try {
      resolvedPort = await invoke<number>('restart_sidecar');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Backend failed to start';
      transitionTo('startup-error', msg);
      setErrorMessage(msg);
      return;
    }

    // Brief poll to confirm sidecar is actually listening
    try {
      resolvedPort = await waitForSidecarPort();
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Backend failed to start';
      transitionTo('startup-error', msg);
      setErrorMessage(msg);
      return;
    }

    setPort(resolvedPort);
    await pollForReady(resolvedPort);
  }, [transitionTo, pollForReady]);

  const retrySidecar = useCallback(async () => {
    if (!isTauriEnvironment()) {
      transitionTo('ready');
      return;
    }

    transitionTo('starting-sidecar');

    let resolvedPort: number;
    try {
      resolvedPort = await invoke<number>('restart_sidecar');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Backend failed to start';
      transitionTo('startup-error', msg);
      setErrorMessage(msg);
      return;
    }
    setPort(resolvedPort);
    await pollForReady(resolvedPort);
  }, [transitionTo, pollForReady]);

  const goToOnboarding = useCallback(() => {
    transitionTo('onboarding');
  }, [transitionTo]);

  return { phase, port, statusMessage, errorMessage, onOnboardingComplete, retrySidecar, goToOnboarding };
}
