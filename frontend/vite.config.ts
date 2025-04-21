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
    // If HMR isn't working reliably in Docker, enable polling
    watch: {
      usePolling: true, // Set to true if needed, otherwise false might be faster
      interval: 1000 // Check for changes every second if polling is enabled
    },
    // WebSocket proxy for development
    proxy: {
      '/ws': {
        // Target the backend service name and port defined in docker-compose
        target: 'ws://backend:8000',
        ws: true, // Enable WebSocket proxying
        changeOrigin: true, // Recommended for virtual hosted sites
        // Optional: Secure WebSocket (wss) if backend uses TLS
        // secure: false,
        // Optional: Log proxy requests
        // logLevel: 'debug',
      }
    }
  },
  // Preview server config (used after building)
  preview: {
    port: 5173, // Match the development port or choose another
    host: true, // Allow external access to preview
  },
  resolve: {
    alias: {
      // Setup '@' alias to point to the 'src' directory
      '@': path.resolve(__dirname, './src'),
      // Explicitly alias buffer for browser compatibility
      'buffer': 'buffer/', // Ensure trailing slash matches polyfill expectations
    },
  },
  // Optimize dependencies and add Node.js polyfills for browser compatibility
  optimizeDeps: {
    // Optimize Plotly dependencies
    include: ['react-plotly.js', 'plotly.js'],
    esbuildOptions: {
      // Define global to globalThis so polyfills can hook properly
      define: {
        global: 'globalThis'
      },
      // Add esbuild plugins for polyfills
      plugins: [
        NodeGlobalsPolyfillPlugin({
            process: true, // Polyfill process if needed by dependencies
            buffer: true,  // Polyfill Buffer
        }),
        NodeModulesPolyfillPlugin() // Polyfills Node.js core modules
      ]
    }
  },
   build: {
    rollupOptions: {
      plugins: [
        // NodeModulesPolyfillPlugin() // Also add polyfill plugin for build if needed
      ],
    },
    // Optional: Increase chunk size warning limit if needed
    // chunkSizeWarningLimit: 1000,
  }
})