import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    // Bind-mounted files on Docker Desktop don't always emit fs events; polling keeps HMR reliable.
    watch: { usePolling: true, interval: 300 },
    proxy: {
      '/api': process.env.BACKEND_URL || 'http://localhost:8000',
    },
  },
})
