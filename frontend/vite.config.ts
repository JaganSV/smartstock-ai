/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    // Needed for file-change detection when running in a Docker bind mount / on Windows.
    watch: { usePolling: true },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/**/*.test.{ts,tsx}',
        'src/test/**',
        'src/api/schema.d.ts',
        'src/main.tsx',
        'src/vite-env.d.ts',
      ],
      reporter: ['text', 'text-summary'],
      // BOB-P4-01: frontend line coverage at least 80%.
      thresholds: { lines: 80 },
    },
  },
});
