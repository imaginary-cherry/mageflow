import type { TestProject } from "vitest/node";
import type { ChildProcess } from "child_process";
import { GenericContainer, type StartedTestContainer } from "testcontainers";
import { startSidecar, waitForServer } from "./serverManager.js";
import { projectRoot, mageVoyanceRoot } from "./seedManager.js";

let redisContainer: StartedTestContainer | null = null;
let serverProcess: ChildProcess | null = null;
let authServerProcess: ChildProcess | null = null;

const IPC_TOKEN = "test-integration-ipc-token";

/**
 * Global setup for integration tests.
 * 1. Starts a Redis testcontainer (random port)
 * 2. Starts a no-auth sidecar (port 8089) — for existing tests
 * 3. Starts an IPC-auth sidecar (port 8090) — for authenticated flow tests
 * Both sidecars receive secrets via stdin, matching the real Tauri delivery.
 */
export default async function setup(project: TestProject): Promise<() => Promise<void>> {
  const port = 8089;
  const authPort = 8090;
  const serverUrl = `http://127.0.0.1:${port}`;
  const authServerUrl = `http://127.0.0.1:${authPort}`;

  // 1. Start Redis container
  console.log("Starting Redis testcontainer...");
  redisContainer = await new GenericContainer("redis/redis-stack-server:7.2.0-v10")
    .withExposedPorts(6379)
    .start();
  const redisHost = redisContainer.getHost();
  const redisPort = redisContainer.getMappedPort(6379);
  const redisUrl = `redis://${redisHost}:${redisPort}`;
  console.log(`Redis ready at ${redisUrl}`);
  process.env.REDIS_URL = redisUrl;

  // 2. Start no-auth sidecar (secrets via stdin, no IPC token)
  console.log(`Starting sidecar on port ${port}...`);
  serverProcess = await startSidecar(port, mageVoyanceRoot, projectRoot, redisUrl);
  try {
    await waitForServer(`${serverUrl}/api/health`, serverProcess, 30000);
    console.log(`Sidecar ready at ${serverUrl}`);
  } catch (error) {
    serverProcess.kill();
    await redisContainer.stop();
    throw new Error(
      `Failed to start sidecar: ${error instanceof Error ? error.message : String(error)}`
    );
  }

  // 3. Start IPC-auth sidecar (secrets + IPC token via stdin)
  console.log(`Starting IPC-auth sidecar on port ${authPort}...`);
  authServerProcess = await startSidecar(authPort, mageVoyanceRoot, projectRoot, redisUrl, IPC_TOKEN);
  try {
    await waitForServer(`${authServerUrl}/api/health`, authServerProcess, 30000);
    console.log(`IPC-auth sidecar ready at ${authServerUrl}`);
  } catch (error) {
    authServerProcess.kill();
    serverProcess.kill();
    await redisContainer.stop();
    throw new Error(
      `Failed to start auth sidecar: ${error instanceof Error ? error.message : String(error)}`
    );
  }

  // @ts-expect-error - Vitest provide API not fully typed
  project.provide("serverUrl", serverUrl);
  // @ts-expect-error - Vitest provide API not fully typed
  project.provide("authServerUrl", authServerUrl);
  // @ts-expect-error - Vitest provide API not fully typed
  project.provide("ipcToken", IPC_TOKEN);

  return async () => {
    if (authServerProcess) {
      authServerProcess.kill("SIGTERM");
      authServerProcess = null;
    }
    if (serverProcess) {
      serverProcess.kill("SIGTERM");
      serverProcess = null;
    }
    if (redisContainer) {
      console.log("Shutting down Redis container...");
      await redisContainer.stop();
      redisContainer = null;
    }
  };
}
