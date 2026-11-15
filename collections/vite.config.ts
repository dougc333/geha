import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5178, host: '127.0.0.1' },
  preview: { port: 5178, host: '127.0.0.1' },
  define: { __COLLECTIONS_API__: JSON.stringify('http://127.0.0.1:8520') },
})
