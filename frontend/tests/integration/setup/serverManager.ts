import { spawn, type ChildProcess } from "child_process";

/**
 * Start the FastAPI server for integration tests
 * @param port Port to run server on
 * @param projectRoot Root directory of the project (repo root)
 * @returns ChildProcess for the spawned server
 */
export function startServer(port: number, projectRoot: string): ChildProcess {
  const redisUrl = process.env.REDIS_URL || "redis://localhost:6379";

  const serverProcess = spawn(
    "uvicorn",
    [
      "mageflow.visualizer.server:create_dev_app",
      "--factory",
      "--host",
      "127.0.0.1",
      "--port",
      port.toString(),
    ],
    {
      cwd: projectRoot,
      env: {
        ...process.env,
        REDIS_URL: redisUrl,
      },
      stdio: ["ignore", "inherit", "inherit"],
    }
  );

  return serverProcess;
}

/**
 * Wait for server to be ready by polling health endpoint
 * @param url Base URL of the server
 * @param timeoutMs Maximum time to wait in milliseconds
 */
export async function waitForServer(
  url: string,
  timeoutMs: number = 10000
): Promise<void> {
  const startTime = Date.now();
  const pollInterval = 200;

  while (Date.now() - startTime < timeoutMs) {
    try {
      const response = await fetch(url);
      if (response.ok) {
        return;
      }
    } catch (error) {
      // Server not ready yet, continue polling
    }

    await new Promise((resolve) => setTimeout(resolve, pollInterval));
  }

  throw new Error(`Server not ready after ${timeoutMs}ms`);
}
