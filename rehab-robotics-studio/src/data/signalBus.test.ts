import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync, symlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { describe, it } from 'node:test';
import { createServer } from 'vite';

import type { CanonicalSignalDataSource } from './DataSource.js';
import type { CanonicalSignalRejectionMetadata } from './DataSource.js';
import type { CanonicalSignalSample } from '../types/signals.js';
import { parseCanonicalSignalSample } from './signalContract.js';

const fixture = JSON.parse(readFileSync(
  join(process.cwd(), '../backend/test/fixtures/signal_contract_cases.json'),
  'utf8',
)) as { base_input: Record<string, unknown> };

function sampleFor(
  mac: string,
  overrides: Readonly<Record<string, unknown>> = {},
): CanonicalSignalSample {
  const input = structuredClone(fixture.base_input);
  input.device_id = `esp32:${mac}`;
  Object.assign(input, overrides);
  const parsed = parseCanonicalSignalSample(input, `mac_${mac}`);
  if (!parsed.ok) throw new Error(`sample fixture rejected: ${parsed.reason}`);
  return parsed.value;
}

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
      const rejected: CanonicalSignalRejectionMetadata[] = [];
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

describe('SignalBus canonical snapshot', () => {
  it('publishes immutable latest-by-MAC state at the render cadence and retains bounded rejections', async () => {
    const temporaryRoot = mkdtempSync(join(tmpdir(), 'rehab-signal-bus-'));
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
      type RejectionState = CanonicalSignalRejectionMetadata & {
        readonly last_update_rejected: boolean;
      };
      type Snapshot = {
        readonly canonicalSamplesByMac: Readonly<Record<string, CanonicalSignalSample>>;
        readonly canonicalAcceptedCount: number;
        readonly canonicalRejectedCount: number;
        readonly canonicalRejectionsBySource: Readonly<Record<string, RejectionState>>;
      };
      const module = await vite.ssrLoadModule('/src/data/signalBus.ts') as {
        SignalBus: new (options: Record<string, unknown>) => {
          dispose(): void;
          subscribe(callback: () => void): () => void;
          getSnapshot(): Snapshot;
        };
      };
      let onAccepted: ((sample: CanonicalSignalSample) => void) | null = null;
      let onRejected: ((rejection: CanonicalSignalRejectionMetadata) => void) | null = null;
      let scheduledFrame: FrameRequestCallback | null = null;
      let canonicalCleanupCount = 0;
      let handle = 0;
      const bus = new module.SignalBus({
        subscribeFrames: () => () => undefined,
        getGraph: () => ({ nodes: [], edges: [] }),
        getLiveKneeAngle: () => ({ state: 'waiting', valueDeg: null, reason: 'Waiting' }),
        subscribeLiveKneeAngle: () => () => undefined,
        subscribeCanonicalAccepted: (callback: (sample: CanonicalSignalSample) => void) => {
          onAccepted = callback;
          return () => { canonicalCleanupCount += 1; };
        },
        subscribeCanonicalRejected: (
          callback: (rejection: CanonicalSignalRejectionMetadata) => void,
        ) => {
          onRejected = callback;
          return () => { canonicalCleanupCount += 1; };
        },
        requestFrame: (callback: FrameRequestCallback) => {
          scheduledFrame = callback;
          return ++handle;
        },
        cancelFrame: () => undefined,
      });
      let notifications = 0;
      bus.subscribe(() => { notifications += 1; });
      assert.ok(onAccepted);
      assert.ok(onRejected);
      const emitAccepted = onAccepted as (sample: CanonicalSignalSample) => void;
      const emitRejected = onRejected as (rejection: CanonicalSignalRejectionMetadata) => void;
      const tick = (timestamp: number) => {
        const callback = scheduledFrame as FrameRequestCallback | null;
        assert.ok(callback);
        callback(timestamp);
      };

      const macA = 'aabbccddeeff';
      const macB = '001122334455';
      for (let sequence = 0; sequence < 100; sequence += 1) {
        emitAccepted(sampleFor(sequence % 2 === 0 ? macA : macB, { sequence }));
      }
      assert.equal(bus.getSnapshot().canonicalAcceptedCount, 0, 'ingest must not publish synchronously');
      assert.equal(notifications, 0);
      tick(34);

      const firstPublished = bus.getSnapshot();
      assert.equal(notifications, 1);
      assert.equal(firstPublished.canonicalAcceptedCount, 100);
      assert.deepEqual(Object.keys(firstPublished.canonicalSamplesByMac).sort(), [
        `esp32:${macB}`,
        `esp32:${macA}`,
      ].sort());
      assert.equal(firstPublished.canonicalSamplesByMac[`esp32:${macA}`].sequence, 98);
      assert.equal(firstPublished.canonicalSamplesByMac[`esp32:${macB}`].sequence, 99);
      assert.equal(Object.isFrozen(firstPublished.canonicalSamplesByMac), true);
      assert.equal(Object.isFrozen(firstPublished.canonicalSamplesByMac[`esp32:${macA}`]), true);
      assert.equal(Object.isFrozen(firstPublished.canonicalSamplesByMac[`esp32:${macA}`].raw), true);

      const retainedSample = firstPublished.canonicalSamplesByMac[`esp32:${macA}`];
      emitRejected({
        device_id: `esp32:${macA}`,
        reason: 'schema_invalid',
        rejected_at_ms: 200,
        count: 1,
        should_announce: true,
      });
      assert.equal(notifications, 1);
      tick(68);
      const rejectedOnce = bus.getSnapshot();
      assert.equal(rejectedOnce.canonicalSamplesByMac[`esp32:${macA}`], retainedSample);
      assert.equal(rejectedOnce.canonicalRejectedCount, 1);
      assert.deepEqual(rejectedOnce.canonicalRejectionsBySource[`esp32:${macA}`], {
        device_id: `esp32:${macA}`,
        reason: 'schema_invalid',
        rejected_at_ms: 200,
        count: 1,
        should_announce: true,
        last_update_rejected: true,
      });

      emitRejected({
        device_id: `esp32:${macA}`,
        reason: 'schema_invalid',
        rejected_at_ms: 201,
        count: 2,
        should_announce: true,
      });
      emitRejected({
        device_id: null,
        reason: 'device_id_invalid',
        rejected_at_ms: 202,
        count: Number.MAX_SAFE_INTEGER,
        should_announce: true,
      });
      tick(102);
      const rejectedAgain = bus.getSnapshot();
      assert.equal(rejectedAgain.canonicalRejectedCount, 3);
      assert.equal(rejectedAgain.canonicalRejectionsBySource[`esp32:${macA}`].should_announce, false);
      assert.equal(rejectedAgain.canonicalRejectionsBySource.unknown.count, Number.MAX_SAFE_INTEGER);
      assert.equal(rejectedAgain.canonicalSamplesByMac.unknown, undefined);
      assert.equal(Object.isFrozen(rejectedAgain.canonicalRejectionsBySource), true);
      assert.equal(Object.isFrozen(rejectedAgain.canonicalRejectionsBySource.unknown), true);

      // A reconnect epoch explicitly permits a new low sequence without joining sessions.
      emitAccepted(sampleFor(macA, { sequence: 0, reconnect_epoch: 3 }));
      tick(136);
      const reconnected = bus.getSnapshot();
      assert.equal(reconnected.canonicalSamplesByMac[`esp32:${macA}`].sequence, 0);
      assert.equal(reconnected.canonicalSamplesByMac[`esp32:${macA}`].reconnect_epoch, 3);
      assert.equal(
        reconnected.canonicalRejectionsBySource[`esp32:${macA}`].last_update_rejected,
        false,
      );

      bus.dispose();
      assert.equal(canonicalCleanupCount, 2);
    } finally {
      await vite.close();
      rmSync(temporaryRoot, { recursive: true, force: true });
    }
  });
});
