/**
 * Phase 16-02: Product knee readout must not use custom /opensim/joint_angle.
 */
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import type { BlockInstance, EdgeDefinition } from '../types/blocks.js';
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
    const { nodes } = getDefaultGraphDocument();
    const b8 = nodes.find((n) => n.id === 'B8');
    assert.ok(b8, 'default graph must include B8');
    assert.notEqual(b8.type, 'opensim_ik_live');
    assert.equal(b8.type, 'opensim_ik_waiting');
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
});
