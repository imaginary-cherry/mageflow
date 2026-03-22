import { describe, it } from 'vitest';

describe('Sidecar Binary (integration)', () => {
  it.todo('binary exists at expected path with target triple');
  it.todo('binary starts and listens on specified port');
  it.todo('binary /api/health returns 200');
  it.todo('binary reads HATCHET_API_KEY and REDIS_URL from environment');
  it.todo('binary exits cleanly on SIGTERM');
});
