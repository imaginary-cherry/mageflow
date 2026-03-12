import { describe, it } from 'vitest';

describe('Sidecar Binary (integration)', () => {
  it.todo('binary exists at expected path with target triple');
  it.todo('binary starts and listens on specified port');
  it.todo('binary /api/health returns 200');
  it.todo('binary accepts --hatchet-api-key and --redis-url arguments');
  it.todo('binary exits cleanly on SIGTERM');
});
