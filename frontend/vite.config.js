import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(fileURLToPath(import.meta.url));

const backendTarget = process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    strictPort: true,
    allowedHosts: [
      '3000-iqfgq6l2knys2z6rebw42-277855b3.sg2.manus.computer',
      '3000-i2j7fcms2zm7b7ngn9ydo-9bef3501.sg2.manus.computer',
      '.sg2.manus.computer',
    ],
    open: true,
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true,
      },
      '/health': {
        target: backendTarget,
        changeOrigin: true,
      },
      '/ready': {
        target: backendTarget,
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: '0.0.0.0',
    port: 4173,
    strictPort: true,
    allowedHosts: ['.sg2.manus.computer'],
  },
  build: {
    rollupOptions: {
      input: {
        home: resolve(root, 'index.html'),
        app: resolve(root, 'app.html'),
        qa: resolve(root, 'qa.html'),
      },
    },
  },
});
