import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    port: 25173,
    proxy: {
      // The backend mounts its API at /api/v1 (API_V1_PREFIX in main.py), so the
      // path is passed through unchanged. Rewriting /api away sent every request
      // one level too high and answered 404.
      '/api': {
        target: 'http://localhost:28000',
        changeOrigin: true,
      },
    },
  },
})
