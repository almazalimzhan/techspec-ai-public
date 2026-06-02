import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const proxyTarget = process.env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 8501,
    strictPort: true,
    proxy: {
      '/upload': proxyTarget,
      '/summary': proxyTarget,
      '/json-fields': proxyTarget,
      '/risks': proxyTarget,
      '/ask': proxyTarget,
      '/health': proxyTarget,
      '/ready': proxyTarget,
    },
  },
})
