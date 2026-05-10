import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    // Proxy /api calls to the local backend — prevents "Failed to fetch" in dev
    // when VITE_API_BASE is not set.
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
  resolve: { alias: { "@": "/src" } },
});
