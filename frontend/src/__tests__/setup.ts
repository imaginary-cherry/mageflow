import { beforeAll } from 'vitest';

export const API_BASE_URL = process.env.VITE_API_URL || 'http://localhost:8080/api';

async function waitForServer(maxAttempts = 30, delayMs = 1000): Promise<void> {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      const response = await fetch(`${API_BASE_URL}/health`);
      if (response.ok) {
        console.log('Server is ready');
        return;
      }
    } catch {
      // Server not ready yet
    }
    await new Promise(resolve => setTimeout(resolve, delayMs));
  }
  throw new Error(`Server at ${API_BASE_URL} did not become ready`);
}

beforeAll(async () => {
  await waitForServer();
});
