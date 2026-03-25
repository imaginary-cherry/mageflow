import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react-swc";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    projects: [
      {
        extends: true,
        test: {
          name: "unit",
          environment: "jsdom",
          globals: true,
          setupFiles: ["./src/test/setup.ts"],
          include: ["src/**/*.{test,spec}.{ts,tsx}"],
        },
      },
      {
        extends: true,
        test: {
          name: "integration",
          environment: "node",
          globals: true,
          testTimeout: 30000,
          globalSetup: ["./tests/integration/setup/globalSetup.ts"],
          include: ["tests/integration/**/*.integration.test.ts"],
        },
      },
      {
        extends: true,
        test: {
          name: "component-integration",
          environment: "jsdom",
          globals: true,
          testTimeout: 30000,
          setupFiles: ["./src/test/setup.ts"],
          globalSetup: ["./tests/integration/setup/globalSetup.ts"],
          include: ["tests/integration/**/*.component.test.tsx"],
        },
      },
    ],
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
});
