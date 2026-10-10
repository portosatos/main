import path from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev server: same origin as the API (SPEC §6.1) — /api is proxied to the backend,
// so session cookies work without CORS. In compose nginx does the same (nginx.conf).
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(import.meta.dirname, "src") },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000",
    },
  },
});
