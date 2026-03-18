import { invoke } from '@tauri-apps/api/core';

export interface AppSettings {
  hatchetApiKey: string;
  redisUrl: string;
}

export interface ValidationResult {
  valid: boolean;
  hatchetError?: string;
  redisError?: string;
}

export function isTauriEnvironment(): boolean {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
}

// localStorage keys for browser dev fallback
const LS_KEY = 'mageflow_settings';

export async function loadSettings(): Promise<AppSettings | null> {
  if (!isTauriEnvironment()) {
    // Browser dev fallback: use localStorage
    try {
      const raw = localStorage.getItem(LS_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw) as Partial<AppSettings>;
      if (parsed.hatchetApiKey && parsed.redisUrl) {
        return { hatchetApiKey: parsed.hatchetApiKey, redisUrl: parsed.redisUrl };
      }
      return null;
    } catch {
      return null;
    }
  }

  try {
    const hatchetApiKey = await invoke<string | null>('load_secret', { key: 'hatchetApiKey' });
    const redisUrl = await invoke<string | null>('load_secret', { key: 'redisUrl' });
    if (hatchetApiKey && redisUrl && hatchetApiKey.trim() !== '' && redisUrl.trim() !== '') {
      return { hatchetApiKey, redisUrl };
    }
    return null;
  } catch {
    return null;
  }
}

export async function saveSettings(settings: AppSettings): Promise<void> {
  if (!isTauriEnvironment()) {
    // Browser dev fallback: use localStorage
    localStorage.setItem(LS_KEY, JSON.stringify(settings));
    return;
  }

  await invoke('save_secret', { key: 'hatchetApiKey', value: settings.hatchetApiKey });
  await invoke('save_secret', { key: 'redisUrl', value: settings.redisUrl });
}

export async function hasSettings(): Promise<boolean> {
  const result = await loadSettings();
  return result !== null;
}

export async function validateCredentials(settings: AppSettings): Promise<ValidationResult> {
  // When not in Tauri environment (browser dev mode), skip validation
  if (!isTauriEnvironment()) {
    return { valid: true };
  }

  try {
    // Temporarily save settings, restart sidecar with new credentials, poll health endpoint
    // Use Option A: invoke restart_sidecar which will use provided credentials, then poll /api/health
    // We pass settings inline via a dedicated validate command if available, otherwise fall back to
    // saving settings temporarily and restarting

    // Attempt to use a validate-credentials Tauri command if available
    try {
      const result = await invoke<{ hatchet: string; redis: string }>('validate_credentials', {
        hatchetApiKey: settings.hatchetApiKey,
        redisUrl: settings.redisUrl,
      });

      const hatchetError = result.hatchet !== 'ok' ? result.hatchet : undefined;
      const redisError = result.redis !== 'ok' ? result.redis : undefined;
      const valid = !hatchetError && !redisError;

      return { valid, hatchetError, redisError };
    } catch (invokeErr) {
      // validate_credentials command not yet available — fall back to restart_sidecar approach
      // Save settings, restart sidecar, poll health, check per-service status
      await saveSettings(settings);
      const port = await invoke<number>('restart_sidecar');
      const healthUrl = `http://127.0.0.1:${port}/api/health`;

      // Poll up to 10s for health endpoint
      let lastErr: Error | null = null;
      for (let i = 0; i < 20; i++) {
        await new Promise(resolve => setTimeout(resolve, 500));
        try {
          const resp = await fetch(healthUrl);
          if (resp.ok) {
            const data = await resp.json() as {
              hatchet?: string;
              redis?: string;
            };
            const hatchetError = data.hatchet && data.hatchet !== 'connected' ? `Could not connect to Hatchet: ${data.hatchet}` : undefined;
            const redisError = data.redis && data.redis !== 'connected' ? `Could not connect to Redis at this URL` : undefined;
            const valid = !hatchetError && !redisError;
            return { valid, hatchetError, redisError };
          }
        } catch (e) {
          lastErr = e as Error;
        }
      }

      return {
        valid: false,
        hatchetError: 'Could not reach sidecar health check',
        redisError: lastErr?.message,
      };
    }
  } catch (err) {
    return {
      valid: false,
      hatchetError: `Validation failed: ${err instanceof Error ? err.message : String(err)}`,
    };
  }
}
