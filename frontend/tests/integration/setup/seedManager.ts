import { spawn } from "child_process";
import { existsSync } from "fs";
import path from "path";

export const projectRoot = path.resolve(import.meta.dirname, "../../../../");
export const mageVoyanceRoot = path.join(projectRoot, "libs", "mage-voyance");

function findPython(): string {
  const venvPython = path.join(projectRoot, ".venv", "bin", "python");
  if (existsSync(venvPython)) {
    return venvPython;
  }
  return "python";
}

/**
 * Seed test data into Redis using Python seed script
 * @param cwd Working directory for the Python process
 */
export async function seedTestData(cwd: string): Promise<void> {
  const redisUrl = process.env.REDIS_URL || "redis://localhost:6379";

  return new Promise((resolve, reject) => {
    let stderr = "";

    const seedProcess = spawn(
      findPython(),
      [
        "-m",
        "integration.frontend.seed_test_data",
        "--action",
        "seed",
        "--redis-url",
        redisUrl,
      ],
      {
        cwd,
        env: process.env,
      }
    );

    seedProcess.stderr.on("data", (data) => {
      stderr += data.toString();
    });

    seedProcess.on("exit", (code) => {
      if (code === 0) {
        resolve();
      } else {
        reject(
          new Error(`Seed script failed with code ${code}: ${stderr.trim()}`)
        );
      }
    });

    seedProcess.on("error", (error) => {
      reject(new Error(`Failed to spawn seed script: ${error.message}`));
    });
  });
}

/**
 * Clean up test data from Redis using Python cleanup script
 * @param cwd Working directory for the Python process
 */
export async function cleanupTestData(cwd: string): Promise<void> {
  const redisUrl = process.env.REDIS_URL || "redis://localhost:6379";

  return new Promise((resolve, reject) => {
    let stderr = "";

    const cleanupProcess = spawn(
      findPython(),
      [
        "-m",
        "integration.frontend.seed_test_data",
        "--action",
        "cleanup",
        "--redis-url",
        redisUrl,
      ],
      {
        cwd,
        env: process.env,
      }
    );

    cleanupProcess.stderr.on("data", (data) => {
      stderr += data.toString();
    });

    cleanupProcess.on("exit", (code) => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`Cleanup script failed with code ${code}: ${stderr.trim()}`));
      }
    });

    cleanupProcess.on("error", (error) => {
      reject(new Error(`Failed to spawn cleanup script: ${error.message}`));
    });
  });
}
