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
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;
          if (
            id.includes('/@blocknote/') ||
            id.includes('/prosemirror-') ||
            id.includes('/yjs/')
          ) {
            return 'editor-rich-text';
          }
          if (id.includes('/@dnd-kit/')) return 'editor-dnd';
          if (id.includes('/@mantine/')) return 'mantine';
          if (id.includes('/react') || id.includes('/react-dom')) {
            return 'react-vendor';
          }
          return undefined;
        },
      },
    },
  },
  server: {
    host: true,
    port: 5173,
    // The backend's Playwright PDF renderer reaches the dev server by its
    // Docker service name ("frontend"). Vite blocks unknown Host headers by
    // default, so without this the print route returns 403 and the PDF falls
    // back to the plain ReportLab renderer after a long timeout.
    allowedHosts: ['frontend'],
    proxy: {
      '/api': { target: apiTarget, changeOrigin: true },
    },
  },
});
