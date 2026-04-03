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

/**
 * Start the real sidecar entry point (visualizer.__main__) with secrets
 * delivered via stdin, matching how Tauri delivers them in the packaged app.
 */
export async function startSidecar(
  port: number,
  cwd: string,
  projectRoot: string,
  redisUrl: string,
  ipcToken?: string | null,
): Promise<ChildProcess> {
  const inUse = await checkPortInUse(port);
  if (inUse) {
    throw new Error(
      `Port ${port} is already in use. Kill the existing process: lsof -ti:${port} | xargs kill`
    );
  }

  const serverProcess = spawn(
    findPython(projectRoot),
    ["-m", "visualizer", "--port", port.toString(), "--host", "127.0.0.1"],
    {
      cwd,
      env: process.env,
      stdio: ["pipe", "inherit", "pipe"],
    }
  );

  const payload = JSON.stringify({
    secrets: { redisUrl, hatchetApiKey: "" },
    ipc_token: ipcToken ?? null,
  }) + "\n";

  serverProcess.stdin?.write(payload);
  serverProcess.stdin?.end();

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
