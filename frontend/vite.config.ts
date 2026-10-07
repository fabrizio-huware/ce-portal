/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In sviluppo le chiamate /api vengono inoltrate al backend locale.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": process.env.VITE_PROXY_TARGET ?? "http://localhost:8000" } },
  preview: { port: 4173, proxy: { "/api": process.env.VITE_PROXY_TARGET ?? "http://localhost:8000" } },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
    css: false,
    exclude: ["e2e/**", "node_modules/**"],
  },
});
