import { describe, it } from 'vitest';

describe('useAppStartup', () => {
  describe('phase transitions', () => {
    it.todo('starts in loading-settings phase');
    it.todo('transitions to onboarding when no settings found');
    it.todo('transitions to starting-sidecar when settings exist');
    it.todo('transitions to connecting-hatchet after sidecar port acquired');
    it.todo('transitions to connecting-redis after hatchet health ok');
    it.todo('transitions to ready after full health check passes');
    it.todo('transitions to startup-error after 30s timeout');
  });

  describe('tray status updates', () => {
    it.todo('calls set_tray_status with starting during sidecar phase');
    it.todo('calls set_tray_status with connected when ready');
    it.todo('calls set_tray_status with disconnected on error');
  });

  describe('callbacks', () => {
    it.todo('onOnboardingComplete restarts sidecar and re-polls');
    it.todo('retrySidecar restarts and re-polls');
  });

  describe('browser dev mode', () => {
    it.todo('skips invoke calls when not in Tauri environment');
  });
});
