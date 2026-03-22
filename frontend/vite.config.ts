import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";

const host = process.env.TAURI_DEV_HOST;

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  clearScreen: false,
  server: {
    host: host || "::",
    port: 8080,
    strictPort: true,
    hmr: host ? { protocol: "ws", host, port: 1421 } : { overlay: false },
    watch: { ignored: ["**/src-tauri/**"] },
  },
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  envPrefix: ["VITE_", "TAURI_ENV_*"],
  build: {
    target:
      process.env.TAURI_ENV_PLATFORM === "windows" ? "chrome105" : "safari13",
    minify: !process.env.TAURI_ENV_DEBUG ? "esbuild" : false,
    sourcemap: !!process.env.TAURI_ENV_DEBUG,
    outDir: "dist",
  },
}));
