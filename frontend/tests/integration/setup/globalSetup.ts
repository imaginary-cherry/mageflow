import type { TestProject } from "vitest/node";
import type { ChildProcess } from "child_process";
import { startServer, waitForServer } from "./serverManager.js";
import { projectRoot } from "./seedManager.js";

let serverProcess: ChildProcess | null = null;

/**
 * Global setup for integration tests
 * Spawns FastAPI server and waits for it to be ready
 * Returns teardown function that kills the server
 */
export default async function setup(project: TestProject): Promise<() => Promise<void>> {
  const port = 8089;
  const serverUrl = `http://127.0.0.1:${port}`;
  const healthUrl = `${serverUrl}/api/health`;

  console.log(`Starting FastAPI server on port ${port}...`);
  serverProcess = startServer(port, projectRoot);

  try {
    await waitForServer(healthUrl, 15000);
    console.log(`FastAPI server ready at ${serverUrl}`);
  } catch (error) {
    serverProcess.kill();
    throw new Error(
      `Failed to start FastAPI server: ${error instanceof Error ? error.message : String(error)}`
    );
  }

  // @ts-ignore - Vitest provide API not fully typed
  project.provide("serverUrl", serverUrl);

  return async () => {
    if (serverProcess) {
      console.log("Shutting down FastAPI server...");
      serverProcess.kill("SIGTERM");
      await new Promise((resolve) => setTimeout(resolve, 500));
      serverProcess = null;
    }
  };
}
