// frontend/vite.config.ts

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path' // Import the 'path' module for resolving paths

// esbuild plugins to polyfill Node globals and modules
import { NodeGlobalsPolyfillPlugin } from '@esbuild-plugins/node-globals-polyfill'
import { NodeModulesPolyfillPlugin } from '@esbuild-plugins/node-modules-polyfill'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Make the server accessible externally (needed for Docker)
    host: true,
    // Port matching docker-compose.yml and EXPOSE in Dockerfile
    port: 5173,
    allowedHosts: ['4ce9-34-17-20-53.ngrok-free.app'], // Added allowed host
    // Optional: Enable polling for file changes if HMR isn't working reliably in Docker
    watch: {
      usePolling: true,
      interval: 1000 // Check for changes every second
    }
  },
  resolve: {
    alias: {
      // Setup '@' alias to point to the 'src' directory
      '@': path.resolve(__dirname, './src'),
      // Alias the `buffer/` import to the browser-compatible buffer package
      buffer: 'buffer'
    },
  },
  // Optimize dependencies and add Node.js polyfills for browser compatibility
  optimizeDeps: {
    include: ['react-plotly.js', 'plotly.js'],
    esbuildOptions: {
      // Define global to globalThis so polyfills can hook properly
      define: {
        global: 'globalThis'
      },
      plugins: [
        NodeGlobalsPolyfillPlugin({ buffer: true }),
        NodeModulesPolyfillPlugin()
      ]
    }
  }
})
