import { spawn, type ChildProcess } from "child_process";
import { createConnection } from "net";
import { existsSync } from "fs";
import path from "path";

function checkPortInUse(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const socket = createConnection({ port, host: "127.0.0.1" });
    socket.once("connect", () => {
      socket.destroy();
      resolve(true);
    });
    socket.once("error", () => {
      resolve(false);
    });
  });
}

function findPython(projectRoot: string): string {
  const venvPython = path.join(projectRoot, ".venv", "bin", "python");
  if (existsSync(venvPython)) {
    return venvPython;
  }
  return "python";
}

export async function startServer(port: number, projectRoot: string): Promise<ChildProcess> {
  const inUse = await checkPortInUse(port);
  if (inUse) {
    throw new Error(
      `Port ${port} is already in use. Kill the existing process: lsof -ti:${port} | xargs kill`
    );
  }

  const redisUrl = process.env.REDIS_URL || "redis://localhost:6379";

  const serverProcess = spawn(
    findPython(projectRoot),
    [
      "-m",
      "uvicorn",
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
      stdio: ["ignore", "inherit", "pipe"],
    }
  );

  return serverProcess;
}

export async function waitForServer(
  url: string,
  serverProcess: ChildProcess,
  timeoutMs: number = 10000
): Promise<void> {
  const startTime = Date.now();
  const pollInterval = 200;

  let processDied = false;
  let exitCode: number | null = null;
  let stderrOutput = "";

  const onExit = (code: number | null) => {
    processDied = true;
    exitCode = code;
  };
  serverProcess.once("exit", onExit);
  serverProcess.stderr?.on("data", (data: Buffer) => {
    stderrOutput += data.toString();
    process.stderr.write(data);
  });

  try {
    while (Date.now() - startTime < timeoutMs) {
      if (processDied) {
        const detail = stderrOutput.trim() ? `\nServer stderr:\n${stderrOutput.trim()}` : "";
        throw new Error(`Server process exited with code ${exitCode}${detail}`);
      }

      try {
        const response = await fetch(url);
        if (response.ok) {
          return;
        }
      } catch {
        // Server not ready yet, continue polling
      }

      await new Promise((resolve) => setTimeout(resolve, pollInterval));
    }

    const detail = stderrOutput.trim() ? `\nServer stderr:\n${stderrOutput.trim()}` : "";
    throw new Error(`Server not ready after ${timeoutMs}ms${detail}`);
  } finally {
    serverProcess.removeListener("exit", onExit);
  }
}
