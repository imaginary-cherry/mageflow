import { spawn } from "child_process";
import { existsSync } from "fs";
import path from "path";

export const projectRoot = path.resolve(import.meta.dirname, "../../../../");

function findPython(): string {
  const venvPython = path.join(projectRoot, ".venv", "bin", "python");
  if (existsSync(venvPython)) {
    return venvPython;
  }
  return "python";
}

/**
 * Seed test data into Redis using Python seed script
 * @param projectRoot Root directory of the project
 */
export async function seedTestData(projectRoot: string): Promise<void> {
  const redisUrl = process.env.REDIS_URL || "redis://localhost:6379";

  return new Promise((resolve, reject) => {
    let stderr = "";

    const seedProcess = spawn(
      findPython(),
      [
        "-m",
        "tests.integration.frontend.seed_test_data",
        "--action",
        "seed",
        "--redis-url",
        redisUrl,
      ],
      {
        cwd: projectRoot,
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
 * @param projectRoot Root directory of the project
 */
export async function cleanupTestData(projectRoot: string): Promise<void> {
  const redisUrl = process.env.REDIS_URL || "redis://localhost:6379";

  return new Promise((resolve, reject) => {
    let stderr = "";

    const cleanupProcess = spawn(
      findPython(),
      [
        "-m",
        "tests.integration.frontend.seed_test_data",
        "--action",
        "cleanup",
        "--redis-url",
        redisUrl,
      ],
      {
        cwd: projectRoot,
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
