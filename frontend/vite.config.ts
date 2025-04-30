
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path' // Import the 'path' module for resolving paths

// esbuild plugins to polyfill Node globals and modules
import { NodeGlobalsPolyfillPlugin } from '@esbuild-plugins/node-globals-polyfill'
import { NodeModulesPolyfillPlugin } from '@esbuild-plugins/node-modules-polyfill'

// your ngrok domain
const NGROK_HOST = 'e35f-34-17-86-106.ngrok-free.app'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Make the server accessible externally (needed for Docker/ngrok)
    host: true,
    port: 5173,
    // Enable CORS so browsers will accept cross‐origin scripts
    cors: {
      origin: [
        `http://${NGROK_HOST}`,
        `https://${NGROK_HOST}`
      ],
      methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
      credentials: true
    },
    // If HMR isn't working reliably in Docker/ngrok, enable polling
    watch: {
      usePolling: true,
      interval: 1000
    },
    // Customize the HMR websocket to point at your ngrok URL
    hmr: {
      host: NGROK_HOST,
      protocol: 'wss',
      // clientPort should match the external TLS port (443 for https)
      clientPort: 443
    },
    // WebSocket proxy for backend if needed
    proxy: {
      '/ws': {
        target: 'ws://backend:8000',
        ws: true,
        changeOrigin: true,
      }
    }
  },
  // Preview server config (used after building)
  preview: {
    port: 5173,
    host: true,
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      'buffer': 'buffer/',
    },
  },
  optimizeDeps: {
    include: ['react-plotly.js', 'plotly.js'],
    esbuildOptions: {
      define: {
        global: 'globalThis'
      },
      plugins: [
        NodeGlobalsPolyfillPlugin({
          process: true,
          buffer: true,
        }),
        NodeModulesPolyfillPlugin()
      ]
    }
  },
  build: {
    rollupOptions: {
      plugins: [
        // Add polyfill plugin here if you hit missing modules at build time
      ],
    },
    // chunkSizeWarningLimit: 1000,
  }
})
