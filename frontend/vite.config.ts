import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// In Docker the dev server proxies /api to the backend service ("web").
// Override with VITE_API_PROXY for local (non-Docker) runs, e.g. http://localhost:8000
const apiTarget = process.env.VITE_API_PROXY || 'http://web:8000';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': { target: apiTarget, changeOrigin: true },
    },
  },
});
