import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// The stats API (crawl_dir/src/stats_server.py) listens on 8520.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5180,
    proxy: { '/api': 'http://127.0.0.1:8520' },
  },
})
