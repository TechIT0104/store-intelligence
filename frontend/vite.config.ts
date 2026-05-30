import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies API + SSE to the running api service so `npm run dev` works
// against `docker compose up`. In production, nginx serves the build and proxies.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, "") },
      "/stream": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
  build: { outDir: "dist", sourcemap: false },
});
