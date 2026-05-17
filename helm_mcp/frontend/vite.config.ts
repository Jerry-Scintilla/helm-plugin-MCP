import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],

  // Critical: relative path so assets work under Helm's sub-path mount
  base: './',

  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },

  server: {
    port: 5174,
    cors: true,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/plugin-sdk': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
