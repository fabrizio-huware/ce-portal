import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In sviluppo le chiamate /api vengono inoltrate al backend locale.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
