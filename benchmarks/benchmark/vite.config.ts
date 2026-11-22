import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import { promises as fs } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const resultsRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'results');
const types: Record<string, string> = {
  '.json': 'application/json; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.png': 'image/png',
  '.pdf': 'application/pdf',
};

function insideResults(target: string): boolean {
  const relative = path.relative(resultsRoot, target);
  return relative !== '' && !relative.startsWith('..') && !path.isAbsolute(relative);
}

function benchmarkApi(): Plugin {
  const mount = (server: { middlewares: { use: (handler: (req: import('node:http').IncomingMessage, res: import('node:http').ServerResponse, next: () => void) => void) => void } }) => {
    server.middlewares.use((req, res, next) => {
      void (async () => {
        if (!req.url || req.method !== 'GET') return next();
        const pathname = new URL(req.url, 'http://localhost').pathname;
        if (pathname === '/api/runs') {
          const entries = await fs.readdir(resultsRoot, { withFileTypes: true }).catch(() => []);
          const runs = await Promise.all(entries.filter((entry) => entry.isDirectory()).map(async (entry) => {
            const file = path.join(resultsRoot, entry.name, 'timings.json');
            try {
              const [stat, raw] = await Promise.all([fs.stat(file), fs.readFile(file, 'utf8')]);
              const parsed = JSON.parse(raw) as { results?: Array<{ mode?: string }> };
              return { id: entry.name, modifiedAt: stat.mtime.toISOString(), modes: (parsed.results ?? []).map((item) => item.mode) };
            } catch { return null; }
          }));
          res.setHeader('Content-Type', types['.json']);
          return res.end(JSON.stringify(runs.filter((run) => run !== null).sort((a, b) => b!.modifiedAt.localeCompare(a!.modifiedAt))));
        }
        if (!pathname.startsWith('/api/artifact/')) return next();
        const relative = decodeURIComponent(pathname.slice('/api/artifact/'.length));
        const target = path.resolve(resultsRoot, relative);
        if (!insideResults(target) || !types[path.extname(target)]) {
          res.statusCode = 403; return res.end('Forbidden');
        }
        try {
          const content = await fs.readFile(target);
          res.setHeader('Content-Type', types[path.extname(target)]);
          res.setHeader('Cache-Control', 'no-store');
          return res.end(content);
        } catch {
          res.statusCode = 404; return res.end('Not found');
        }
      })().catch((error: unknown) => {
        res.statusCode = 500;
        res.end(error instanceof Error ? error.message : 'Server error');
      });
    });
  };
  return {
    name: 'local-benchmark-results',
    configureServer: mount,
    configurePreviewServer: mount,
  };
}

export default defineConfig({
  plugins: [react(), benchmarkApi()],
  server: { host: '127.0.0.1', port: 8530, strictPort: true },
  preview: { host: '127.0.0.1', port: 8531, strictPort: true },
});
