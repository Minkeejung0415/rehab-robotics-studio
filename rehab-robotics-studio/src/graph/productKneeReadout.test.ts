/**
 * Phase 16-02: Product knee readout must not use custom /opensim/joint_angle.
 */
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, symlinkSync } from 'node:fs';
import { describe, it } from 'node:test';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createServer } from 'vite';

import type { BlockInstance, EdgeDefinition } from '../types/blocks.js';
import type { LiveKneeAngleSnapshot } from '../types/health.js';
import type { Frame } from '../types/signals.js';
import { runMockExecutor, type ExecMemory } from './mockExecutor.js';
import { getDefaultGraphDocument } from '../state/graphStore.js';

function baseFrame(overrides: Partial<Frame> = {}): Frame {
  return {
    t: 1.0,
    force: { fx: 0, fy: 0, fz: 0, mag: 0, t: 1.0 },
    emg: { raw: 0, envelope: 0, channel: 0, t: 1.0 },
    imu: {
      quat: [1, 0, 0, 0],
      accel: [0, 0, 9.81],
      gyro: [0, 0, 0],
      t: 1.0,
    },
    motor: {
      position: 0,
      velocity: 0,
      torque: 0,
      current: 0,
      temperature: 25,
      enabled: false,
      fault: false,
      t: 1.0,
    },
    ...overrides,
  };
}

describe('product knee readout — custom joint angle retired', () => {
  it('default graph B8 is not opensim_ik_live product IK source', () => {
    const { nodes, edges } = getDefaultGraphDocument();
    const b8 = nodes.find((n) => n.id === 'B8');
    assert.ok(b8, 'default graph must include B8');
    assert.notEqual(b8.type, 'opensim_ik_live');
    assert.equal(b8.type, 'opensim_ik_waiting');
    assert.equal(b8.name, 'OpenSim IK');
    assert.ok(
      edges.some((edge) => (
        edge.sourceBlockId === 'B8'
        && edge.sourcePortId === 'angles'
        && edge.targetBlockId === 'B9'
        && edge.targetPortId === 'angle'
      )),
      'stable B8 angles port must remain wired to the B9 display',
    );
    assert.equal(
      nodes.some((n) => n.type === 'opensim_ik_live'),
      false,
      'default nodes must not include opensim_ik_live',
    );
  });

  it('default graph ignores frame.jointAngleDeg for product knee', () => {
    const { nodes, edges } = getDefaultGraphDocument();
    const mem: ExecMemory = {};
    const result = runMockExecutor(
      nodes,
      edges,
      baseFrame({ jointAngleDeg: 42.5 }),
      mem,
    );
    assert.ok(
      result.knee === undefined
        || result.knee === null
        || !Number.isFinite(result.knee),
      `product knee must not be finite custom angle, got ${String(result.knee)}`,
    );
  });

  it('default B8 passes only finite official values, including a true zero', () => {
    const { nodes, edges } = getDefaultGraphDocument();
    const mem: ExecMemory = {};

    assert.equal(
      runMockExecutor(
        nodes,
        edges,
        baseFrame({ jointAngleDeg: 91, openSimKneeAngleDeg: 27.5 }),
        mem,
      ).knee,
      27.5,
    );
    assert.equal(
      runMockExecutor(
        nodes,
        edges,
        baseFrame({ jointAngleDeg: 91, openSimKneeAngleDeg: 0 }),
        mem,
      ).knee,
      0,
    );

    for (const unavailable of [null, Number.NaN, Number.POSITIVE_INFINITY]) {
      const result = runMockExecutor(
        nodes,
        edges,
        baseFrame({ jointAngleDeg: 91, openSimKneeAngleDeg: unavailable }),
        mem,
      );
      assert.equal(result.knee, undefined);
    }
  });

  it('opensim_ik_live alone does not fake angles=0 when jointAngleDeg absent', () => {
    const nodes: BlockInstance[] = [{
      id: 'L1',
      type: 'opensim_ik_live',
      name: 'debug',
      position: { x: 0, y: 0 },
      params: {},
      status: 'idle',
    }];
    const edges: EdgeDefinition[] = [];
    const mem: ExecMemory = {};
    const result = runMockExecutor(nodes, edges, baseFrame(), mem);
    // No joint_angle_display — still evaluate block by wiring a display
    const withDisplay: BlockInstance[] = [
      ...nodes,
      {
        id: 'D1',
        type: 'joint_angle_display',
        name: 'display',
        position: { x: 0, y: 0 },
        params: {},
        status: 'idle',
      },
    ];
    const wired: EdgeDefinition[] = [{
      id: 'e',
      sourceBlockId: 'L1',
      sourcePortId: 'angles',
      targetBlockId: 'D1',
      targetPortId: 'angle',
      signalType: 'joint_state',
    }];
    const kneeResult = runMockExecutor(withDisplay, wired, baseFrame(), mem);
    assert.ok(
      kneeResult.knee === undefined
        || kneeResult.knee === null
        || !Number.isFinite(kneeResult.knee),
      `opensim_ik_live must fail closed without sample, got ${String(kneeResult.knee)}`,
    );
    void result;
  });

  it('SignalBus clears closed-gate history and starts recovery as a new series', async () => {
    // Vite cannot resolve module URLs when the real workspace path contains
    // "#". A disposable junction plus preserveSymlinks keeps the test portable.
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
      const module = await vite.ssrLoadModule('/src/data/signalBus.ts') as {
        SignalBus: new (options: Record<string, unknown>) => {
          dispose(): void;
          getSnapshot(): {
            kneeAngle: number | null;
            kneeSeries: number[];
          };
        };
      };
      let onFrame: ((frame: Frame) => void) | null = null;
      let onLiveAngle: ((snapshot: LiveKneeAngleSnapshot) => void) | null = null;
      let current: LiveKneeAngleSnapshot = {
        state: 'waiting',
        valueDeg: null,
        reason: 'Waiting for calibrated IK',
      };
      const bus = new module.SignalBus({
        subscribeFrames: (callback: (frame: Frame) => void) => {
          onFrame = callback;
          return () => undefined;
        },
        getGraph: getDefaultGraphDocument,
        getLiveKneeAngle: () => current,
        subscribeLiveKneeAngle: (
          callback: (snapshot: LiveKneeAngleSnapshot) => void,
        ) => {
          onLiveAngle = callback;
          return () => undefined;
        },
        requestFrame: null,
      });

      const publishAngle = (snapshot: LiveKneeAngleSnapshot) => {
        current = snapshot;
        assert.ok(onLiveAngle);
        onLiveAngle(snapshot);
      };
      const publishFrame = (frame: Frame) => {
        assert.ok(onFrame);
        onFrame(frame);
      };

      publishAngle({
        state: 'live',
        valueDeg: 12.5,
        reason: '',
        sourceStamp: { sec: 1, nanosec: 0 },
        receivedAtMs: 1,
      });
      publishFrame(baseFrame({
        jointAngleDeg: 99,
        openSimKneeAngleDeg: 88,
      }));
      assert.equal(bus.getSnapshot().kneeAngle, 12.5);
      assert.deepEqual(bus.getSnapshot().kneeSeries, [12.5]);

      publishAngle({
        state: 'live',
        valueDeg: 0,
        reason: '',
        sourceStamp: { sec: 2, nanosec: 0 },
        receivedAtMs: 2,
      });
      publishFrame(baseFrame({ jointAngleDeg: 99 }));
      assert.equal(bus.getSnapshot().kneeAngle, 0);
      assert.deepEqual(bus.getSnapshot().kneeSeries, [12.5, 0]);

      publishAngle({
        state: 'stale',
        valueDeg: null,
        reason: 'JointState stale - no fresh angle for 2.0 s',
      });
      assert.equal(bus.getSnapshot().kneeAngle, null);
      assert.deepEqual(bus.getSnapshot().kneeSeries, []);

      publishFrame(baseFrame({
        jointAngleDeg: 99,
        openSimKneeAngleDeg: 77,
      }));
      assert.equal(bus.getSnapshot().kneeAngle, null);
      assert.deepEqual(bus.getSnapshot().kneeSeries, []);

      publishAngle({
        state: 'live',
        valueDeg: -8,
        reason: '',
        sourceStamp: { sec: 3, nanosec: 0 },
        receivedAtMs: 3,
      });
      publishFrame(baseFrame({ jointAngleDeg: 99 }));
      assert.equal(bus.getSnapshot().kneeAngle, -8);
      assert.deepEqual(bus.getSnapshot().kneeSeries, [-8]);
      bus.dispose();
    } finally {
      await vite.close();
      rmSync(temporaryRoot, { recursive: true, force: true });
    }
  });

  it('SignalBus cancels its animation frame and cannot reschedule after dispose', async () => {
    const temporaryRoot = mkdtempSync(join(tmpdir(), 'rehab-signal-bus-dispose-'));
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
      const module = await vite.ssrLoadModule('/src/data/signalBus.ts') as {
        SignalBus: new (options: Record<string, unknown>) => {
          dispose(): void;
        };
      };
      let scheduledCallback: FrameRequestCallback | null = null;
      let requestCount = 0;
      const cancelled: number[] = [];
      const bus = new module.SignalBus({
        subscribeFrames: () => () => undefined,
        getGraph: getDefaultGraphDocument,
        getLiveKneeAngle: () => ({
          state: 'waiting',
          valueDeg: null,
          reason: 'Waiting for calibrated IK',
        }),
        subscribeLiveKneeAngle: () => () => undefined,
        requestFrame: (callback: FrameRequestCallback) => {
          requestCount += 1;
          scheduledCallback = callback;
          return 40 + requestCount;
        },
        cancelFrame: (handle: number) => cancelled.push(handle),
      });

      assert.equal(requestCount, 1);
      assert.ok(scheduledCallback);
      const queuedBeforeDispose = scheduledCallback as FrameRequestCallback;
      bus.dispose();
      assert.deepEqual(cancelled, [41]);

      queuedBeforeDispose(100);
      assert.equal(requestCount, 1, 'disposed loop must not schedule another frame');
      bus.dispose();
      assert.deepEqual(cancelled, [41], 'dispose must be idempotent');
    } finally {
      await vite.close();
      rmSync(temporaryRoot, { recursive: true, force: true });
    }
  });
});
