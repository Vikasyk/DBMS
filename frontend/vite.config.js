import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'TRACEFOOD_')
  const proxy = {
    '/api': {
      target: process.env.TRACEFOOD_API_TARGET || env.TRACEFOOD_API_TARGET || 'http://127.0.0.1:8000',
      rewrite: (path) => path.replace(/^\/api(?=\/|$)/, ''),
    },
  }

  return {
    plugins: [react()],
    server: { host: '127.0.0.1', port: 5173, proxy },
    preview: { host: '127.0.0.1', port: 4173, proxy },
    build: {
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (/\/node_modules\/(react(?:-dom|-router(?:-dom)?|-is)?|scheduler)\//.test(id)) return 'react-runtime'
            if (/\/node_modules\/recharts\//.test(id)) return 'charts'
            if (/\/node_modules\/(victory-vendor|d3-[^/]+|es-toolkit)\//.test(id)) return 'chart-math'
          },
        },
      },
    },
  }
})
