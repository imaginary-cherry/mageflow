import { invoke } from '@tauri-apps/api/core';

export interface AppSettings {
  hatchetApiKey: string;
  redisUrl: string;
}

export function isTauriEnvironment(): boolean {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
}

// localStorage keys for browser dev fallback
const LS_KEY = 'mageflow_settings';

// Secret key names — shared with Rust keyring commands
const SECRET_HATCHET_API_KEY = 'hatchetApiKey';
const SECRET_REDIS_URL = 'redisUrl';

export async function loadSettings(): Promise<AppSettings | null> {
  if (!isTauriEnvironment()) {
    // Browser dev fallback: use localStorage
    try {
      const savedSettings = localStorage.getItem(LS_KEY);
      if (!savedSettings) return null;
      const settings = JSON.parse(savedSettings) as Record<string, unknown>;
      const hatchetApiKey = typeof settings.hatchetApiKey === 'string' ? settings.hatchetApiKey : '';
      const redisUrl = typeof settings.redisUrl === 'string' ? settings.redisUrl : '';
      if (hatchetApiKey && redisUrl) {
        return { hatchetApiKey, redisUrl };
      }
      return null;
    } catch {
      return null;
    }
  }

  try {
    const json = await invoke<string | null>('load_all_secrets');
    if (!json) return null;
    const secrets = JSON.parse(json) as Record<string, unknown>;
    const hatchetApiKey = typeof secrets.hatchetApiKey === 'string' ? secrets.hatchetApiKey : '';
    const redisUrl = typeof secrets.redisUrl === 'string' ? secrets.redisUrl : '';
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

  await invoke('save_secret', { key: SECRET_HATCHET_API_KEY, value: settings.hatchetApiKey });
  await invoke('save_secret', { key: SECRET_REDIS_URL, value: settings.redisUrl });
}

export async function clearSettings(): Promise<void> {
  if (!isTauriEnvironment()) {
    localStorage.removeItem(LS_KEY);
    return;
  }

  await invoke('save_secret', { key: SECRET_HATCHET_API_KEY, value: '' });
  await invoke('save_secret', { key: SECRET_REDIS_URL, value: '' });
}
