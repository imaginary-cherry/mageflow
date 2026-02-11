import type { TestProject } from "vitest/node";
import type { ChildProcess } from "child_process";
import { startServer, waitForServer } from "./serverManager.js";
import { projectRoot } from "./seedManager.js";

let serverProcess: ChildProcess | null = null;

/**
 * Global setup for integration tests
 * Spawns Redis container and FastAPI server via Python script
 * Returns teardown function that kills the server and container
 */
export default async function setup(project: TestProject): Promise<() => Promise<void>> {
  const port = 8089;
  const serverUrl = `http://127.0.0.1:${port}`;
  const healthUrl = `${serverUrl}/api/health`;

  console.log(`Starting Redis container and FastAPI server on port ${port}...`);
  serverProcess = await startServer(port, projectRoot);

  try {
    await waitForServer(healthUrl, serverProcess, 30000);
    console.log(`FastAPI server ready at ${serverUrl}`);
  } catch (error) {
    serverProcess.kill();
    throw new Error(
      `Failed to start server: ${error instanceof Error ? error.message : String(error)}`
    );
  }

  // @ts-expect-error - Vitest provide API not fully typed
  project.provide("serverUrl", serverUrl);

  return async () => {
    if (serverProcess) {
      console.log("Shutting down server and Redis container...");
      serverProcess.kill("SIGTERM");
      await new Promise((resolve) => setTimeout(resolve, 2000));
      serverProcess = null;
    }
  };
}
