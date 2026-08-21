import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { existsSync } from 'node:fs';
import { dirname, extname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

function extensionlessRelativeResolver() {
  return {
    name: 'extensionless-relative-resolver',
    resolveId(source: string, importer?: string) {
      if (!importer || !source.startsWith('.') || extname(source)) return null;
      const base = importer.startsWith('file:') ? fileURLToPath(importer) : importer;
      const candidate = resolve(dirname(base), source);
      for (const extension of ['.tsx', '.ts', '.jsx', '.js']) {
        const file = `${candidate}${extension}`;
        if (existsSync(file)) return file;
      }
      for (const extension of ['.tsx', '.ts', '.jsx', '.js']) {
        const file = resolve(candidate, `index${extension}`);
        if (existsSync(file)) return file;
      }
      return null;
    },
  };
}

export default defineConfig({
  plugins: [extensionlessRelativeResolver(), react()],
  server: { port: 5173 },
});
