import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies the trace API (python server.py on :8765).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8765" } },
});
