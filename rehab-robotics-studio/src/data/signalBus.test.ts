import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, symlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { describe, it } from 'node:test';
import { createServer } from 'vite';

import type { CanonicalSignalDataSource } from './DataSource.js';
import type { CanonicalSignalRejection } from './RosbridgeDataSource.js';
import type { CanonicalSignalSample } from '../types/signals.js';

describe('application canonical data-source subscriptions', () => {
  it('forwards accepted and rejected events independently and cleans up both listeners', async () => {
    const temporaryRoot = mkdtempSync(join(tmpdir(), 'rehab-app-source-'));
    const projectLink = join(temporaryRoot, 'studio');
    symlinkSync(process.cwd(), projectLink, 'junction');
    const vite = await createServer({
      root: projectLink,
      configFile: false,
      appType: 'custom',
      resolve: { preserveSymlinks: true },
      optimizeDeps: { noDiscovery: true, include: [] },
      server: { middlewareMode: true },
    });
    try {
      const { appDataSource } = await vite.ssrLoadModule('/src/data/appDataSource.ts') as {
        appDataSource: CanonicalSignalDataSource;
      };
      const canonicalSource: CanonicalSignalDataSource = appDataSource;
      const accepted: CanonicalSignalSample[] = [];
      const rejected: CanonicalSignalRejection[] = [];
      const unsubscribeAccepted = canonicalSource.subscribeCanonicalAccepted((sample) => accepted.push(sample));
      const unsubscribeRejected = canonicalSource.subscribeCanonicalRejected((event) => rejected.push(event));

      // A subscription is explicitly empty until the live parser accepts or rejects input.
      assert.deepEqual(accepted, []);
      assert.deepEqual(rejected, []);
      unsubscribeAccepted();
      unsubscribeRejected();
    } finally {
      await vite.close();
      rmSync(temporaryRoot, { recursive: true, force: true });
    }
  });
});
