import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import type {
  LiveKneeAngleSnapshot,
  OpenSimIkStatusSnapshot,
  OpenSimJointStateSnapshot,
  OpenSimStatusSnapshot,
  RosStamp,
} from '../types/health.js';
import {
  IK_ANGLE_STALE_MS,
  LiveKneeAngleTracker,
  compareRosStamps,
  deriveLiveKneeAngle,
  formatLiveKneeAngle,
  isValidRosStamp,
  normalizeLiveKneeReason,
  selectLiveKneeAngleSeries,
} from './liveKneeAngle.js';

const CALIBRATION_ID = 'cal-19';

function calibratedStatus(
  overrides: Partial<NonNullable<OpenSimStatusSnapshot['calibration']>> = {},
): OpenSimStatusSnapshot {
  return {
    calibration: {
      state: 'CALIBRATED',
      reason: '',
      calibration_id: CALIBRATION_ID,
      ...overrides,
    },
  };
}

function validIk(overrides: Partial<OpenSimIkStatusSnapshot> = {}): OpenSimIkStatusSnapshot {
  return {
    schema: 'rehab.opensim_ik_status.1',
    solution_valid: true,
    reason: '',
    calibration_id: CALIBRATION_ID,
    ...overrides,
  };
}

function jointState(
  radians = Math.PI / 2,
  overrides: Partial<OpenSimJointStateSnapshot> = {},
): OpenSimJointStateSnapshot {
  return {
    stamp: { sec: 10, nanosec: 20 },
    names: ['hip_flexion_r', 'knee_angle_r'],
    positions: [0.25, radians],
    receivedAtMs: 1_000,
    ...overrides,
  };
}

function derive(overrides: Partial<Parameters<typeof deriveLiveKneeAngle>[0]> = {}) {
  return deriveLiveKneeAngle({
    openSimStatus: calibratedStatus(),
    ikStatus: validIk(),
    jointState: jointState(),
    nowMs: 1_000,
    ...overrides,
  });
}

function assertUnavailable(
  snapshot: LiveKneeAngleSnapshot,
  state?: 'waiting' | 'invalid' | 'stale',
): void {
  assert.notEqual(snapshot.state, 'live');
  assert.equal(snapshot.valueDeg, null);
  assert.ok(snapshot.reason.length > 0);
  if (state) assert.equal(snapshot.state, state);
}

describe('live OpenSim knee angle contract', () => {
  it('formats one-decimal live values while keeping valid zero distinct from unavailable', () => {
    assert.deepEqual(formatLiveKneeAngle(12.34), {
      isLive: true,
      valueText: '12.3 deg',
      statusText: null,
    });
    assert.deepEqual(formatLiveKneeAngle(0), {
      isLive: true,
      valueText: '0.0 deg',
      statusText: null,
    });

    for (const unavailable of [null, undefined, Number.NaN, Number.POSITIVE_INFINITY]) {
      assert.deepEqual(formatLiveKneeAngle(unavailable), {
        isLive: false,
        valueText: '—',
        statusText: 'Waiting for calibrated IK',
      });
    }
  });

  it('clears closed or invalid chart history and returns only a new finite live trace', () => {
    const oldTrace = [10, 20];
    assert.deepEqual(selectLiveKneeAngleSeries(null, oldTrace), []);
    assert.deepEqual(selectLiveKneeAngleSeries(Number.NaN, oldTrace), []);
    assert.deepEqual(selectLiveKneeAngleSeries(30, [10, Number.NaN]), []);

    const recoveredTrace = [30];
    assert.equal(selectLiveKneeAngleSeries(30, recoveredTrace), recoveredTrace);
  });

  it('defines the locked 2,000 ms freshness window', () => {
    assert.equal(IK_ANGLE_STALE_MS, 2_000);
  });

  it('uses a 180-degree clinical baseline for the calibrated straight pose', () => {
    const rightAngle = derive();
    assert.equal(rightAngle.state, 'live');
    assert.equal(rightAngle.valueDeg, 90);

    const zero = derive({ jointState: jointState(0) });
    assert.equal(zero.state, 'live');
    assert.equal(zero.valueDeg, 180);
  });

  it('selects knee_angle_r by name when coordinates are reordered', () => {
    const reordered = derive({
      jointState: jointState(0, {
        names: ['knee_angle_r', 'hip_flexion_r', 'ankle_angle_r'],
        positions: [-Math.PI / 4, 0.1, 0.2],
      }),
    });
    assert.equal(reordered.state, 'live');
    assert.equal(reordered.valueDeg, 225);
  });

  it('fails closed when calibration, IK, or identity gates close', () => {
    const cases = [
      derive({ openSimStatus: null }),
      derive({ openSimStatus: calibratedStatus({ state: 'UNCALIBRATED' }) }),
      derive({ openSimStatus: calibratedStatus({ state: 'CAPTURING' }) }),
      derive({ openSimStatus: calibratedStatus({ state: 'FAILED' }) }),
      derive({ ikStatus: null }),
      derive({ ikStatus: validIk({ solution_valid: false, reason: 'solver_unavailable' }) }),
      derive({ openSimStatus: calibratedStatus({ calibration_id: '' }) }),
      derive({ ikStatus: validIk({ calibration_id: '' }) }),
      derive({ ikStatus: validIk({ calibration_id: 'different-cal' }) }),
    ];
    for (const snapshot of cases) assertUnavailable(snapshot);
  });

  it('fails closed for malformed arrays, missing knee, and non-finite positions', () => {
    const cases = [
      derive({ jointState: null }),
      derive({ jointState: jointState(0, { names: ['knee_angle_r'], positions: [] }) }),
      derive({ jointState: jointState(0, { names: ['hip_flexion_r'], positions: [0] }) }),
      derive({ jointState: jointState(0, { positions: [0.25, Number.NaN] }) }),
      derive({ jointState: jointState(0, { positions: [0.25, Number.POSITIVE_INFINITY] }) }),
    ];
    for (const snapshot of cases) assertUnavailable(snapshot);
  });

  it('accepts 1,999 ms receipt age and rejects 2,001 ms as stale', () => {
    const sample = jointState(0, { receivedAtMs: 10_000 });
    assert.equal(derive({ jointState: sample, nowMs: 11_999 }).state, 'live');
    assertUnavailable(derive({ jointState: sample, nowMs: 12_001 }), 'stale');
  });

  it('rejects malformed, unsafe, and out-of-order stamps without nanosecond math', () => {
    const good: RosStamp = { sec: Number.MAX_SAFE_INTEGER, nanosec: 999_999_999 };
    assert.equal(isValidRosStamp(good), true);
    assert.equal(compareRosStamps({ sec: 9, nanosec: 999_999_999 }, { sec: 10, nanosec: 0 }), -1);

    const badStamps: RosStamp[] = [
      { sec: -1, nanosec: 0 },
      { sec: 1.5, nanosec: 0 },
      { sec: Number.MAX_SAFE_INTEGER + 1, nanosec: 0 },
      { sec: 1, nanosec: -1 },
      { sec: 1, nanosec: 1.5 },
      { sec: 1, nanosec: 1_000_000_000 },
    ];
    for (const stamp of badStamps) {
      assert.equal(isValidRosStamp(stamp), false);
      assertUnavailable(derive({ jointState: jointState(0, { stamp }) }), 'invalid');
    }

    assertUnavailable(
      derive({
        jointState: jointState(0, { stamp: { sec: 9, nanosec: 99 } }),
        lastAcceptedStamp: { sec: 10, nanosec: 0 },
      }),
      'invalid',
    );
  });

  it('normalizes only bounded plain-string reasons for the view model', () => {
    assert.equal(normalizeLiveKneeReason('solver_unavailable', 'fallback'), 'Solver unavailable');
    assert.equal(normalizeLiveKneeReason({ secret: true }, 'fallback'), 'fallback');
    assert.equal(normalizeLiveKneeReason('{"secret":true}', 'fallback'), 'fallback');
    assert.equal(normalizeLiveKneeReason('[object Object]', 'fallback'), 'fallback');
    assert.equal(normalizeLiveKneeReason('trace\nline', 'fallback'), 'fallback');
  });
});

describe('LiveKneeAngleTracker timer and transition seam', () => {
  it('cancels and replaces stale timers for each accepted sample', () => {
    let now = 1_000;
    let nextHandle = 0;
    const scheduled = new Map<number, { callback: () => void; delayMs: number }>();
    const cancelled: number[] = [];
    const tracker = new LiveKneeAngleTracker({
      nowMs: () => now,
      schedule: (callback, delayMs) => {
        const handle = ++nextHandle;
        scheduled.set(handle, { callback, delayMs });
        return handle;
      },
      cancel: (handle) => {
        cancelled.push(handle as number);
        scheduled.delete(handle as number);
      },
    });

    tracker.setOpenSimStatus(calibratedStatus());
    tracker.setIkStatus(validIk());
    tracker.setJointState(jointState(0, { receivedAtMs: now, stamp: { sec: 1, nanosec: 0 } }));
    const firstHandle = nextHandle;
    assert.equal(scheduled.get(firstHandle)?.delayMs, 2_001);

    now = 1_500;
    tracker.setJointState(jointState(0.1, { receivedAtMs: now, stamp: { sec: 2, nanosec: 0 } }));
    assert.ok(cancelled.includes(firstHandle));
    assert.equal(scheduled.size, 1);
    assert.equal(tracker.getSnapshot().state, 'live');
    tracker.dispose();
  });

  it('becomes stale from the scheduled callback and recovers with a fresh sample', () => {
    let now = 5_000;
    let callback: (() => void) | null = null;
    const transitions: string[] = [];
    const tracker = new LiveKneeAngleTracker({
      nowMs: () => now,
      schedule: (next) => {
        callback = next;
        return 1;
      },
      cancel: () => {
        callback = null;
      },
      onTransition: (snapshot) => transitions.push(`${snapshot.state}:${snapshot.reason}`),
    });

    tracker.setOpenSimStatus(calibratedStatus());
    tracker.setIkStatus(validIk());
    tracker.setJointState(jointState(Math.PI / 6, {
      receivedAtMs: now,
      stamp: { sec: 1, nanosec: 0 },
    }));
    assert.equal(tracker.getSnapshot().state, 'live');
    assert.ok(callback);

    now += 2_001;
    const expire = callback as unknown as () => void;
    expire();
    assert.equal(tracker.getSnapshot().state, 'stale');

    tracker.setJointState(jointState(Math.PI / 3, {
      receivedAtMs: now,
      stamp: { sec: 2, nanosec: 0 },
    }));
    assert.equal(tracker.getSnapshot().state, 'live');
    assert.ok(Math.abs((tracker.getSnapshot().valueDeg ?? 0) - 120) < 1e-10);
    assert.equal(transitions.filter((entry) => entry.startsWith('stale:')).length, 1);
    tracker.dispose();
  });

  it('clears cached JointState when calibration closes', () => {
    let now = 1_000;
    const tracker = new LiveKneeAngleTracker({
      nowMs: () => now,
      schedule: () => 1,
      cancel: () => undefined,
    });
    tracker.setOpenSimStatus(calibratedStatus());
    tracker.setIkStatus(validIk());
    tracker.setJointState(jointState(0, { receivedAtMs: now }));
    assert.equal(tracker.getSnapshot().state, 'live');

    tracker.setOpenSimStatus(calibratedStatus({ state: 'UNCALIBRATED', calibration_id: null }));
    assertUnavailable(tracker.getSnapshot(), 'waiting');
    tracker.setOpenSimStatus(calibratedStatus());
    assertUnavailable(tracker.getSnapshot(), 'waiting');

    now += 1;
    tracker.setJointState(jointState(0, { receivedAtMs: now, stamp: { sec: 11, nanosec: 0 } }));
    assert.equal(tracker.getSnapshot().state, 'live');
    tracker.dispose();
  });

  it('coalesces identical state/reason notifications but reports real transitions', () => {
    let now = 1_000;
    const transitions: string[] = [];
    const tracker = new LiveKneeAngleTracker({
      nowMs: () => now,
      schedule: () => 1,
      cancel: () => undefined,
      onTransition: (snapshot) => transitions.push(`${snapshot.state}:${snapshot.reason}`),
    });

    tracker.setOpenSimStatus(calibratedStatus());
    tracker.setOpenSimStatus(calibratedStatus());
    tracker.setIkStatus(validIk({ solution_valid: false, reason: 'solver_unavailable' }));
    tracker.setIkStatus(validIk({ solution_valid: false, reason: 'solver_unavailable' }));
    tracker.setIkStatus(validIk());
    tracker.setJointState(jointState(0, { receivedAtMs: now }));
    tracker.setJointState(jointState(0.1, {
      receivedAtMs: now,
      stamp: { sec: 10, nanosec: 21 },
    }));

    assert.equal(
      transitions.filter((entry) => entry === 'invalid:IK invalid - Solver unavailable').length,
      1,
    );
    assert.equal(transitions.filter((entry) => entry.startsWith('live:')).length, 1);
    tracker.dispose();
  });

  it('fails closed on out-of-order samples and recovers on a later ordered sample', () => {
    let now = 1_000;
    const tracker = new LiveKneeAngleTracker({
      nowMs: () => now,
      schedule: () => 1,
      cancel: () => undefined,
    });
    tracker.setOpenSimStatus(calibratedStatus());
    tracker.setIkStatus(validIk());
    tracker.setJointState(jointState(0, {
      receivedAtMs: now,
      stamp: { sec: 10, nanosec: 10 },
    }));
    assert.equal(tracker.getSnapshot().state, 'live');

    tracker.setJointState(jointState(0.2, {
      receivedAtMs: now,
      stamp: { sec: 10, nanosec: 9 },
    }));
    assertUnavailable(tracker.getSnapshot(), 'invalid');

    now += 1;
    tracker.setJointState(jointState(0.3, {
      receivedAtMs: now,
      stamp: { sec: 10, nanosec: 11 },
    }));
    assert.equal(tracker.getSnapshot().state, 'live');
    tracker.dispose();
  });

  it('does not let a malformed high-stamp sample poison the ordering watermark', () => {
    let now = 1_000;
    const tracker = new LiveKneeAngleTracker({
      nowMs: () => now,
      schedule: () => 1,
      cancel: () => undefined,
    });
    tracker.setOpenSimStatus(calibratedStatus());
    tracker.setIkStatus(validIk());
    tracker.setJointState(jointState(0, {
      receivedAtMs: now,
      stamp: { sec: 10, nanosec: 0 },
    }));

    tracker.setJointState(jointState(0, {
      names: ['hip_flexion_r'],
      positions: [0],
      receivedAtMs: now,
      stamp: { sec: 999, nanosec: 0 },
    }));
    assertUnavailable(tracker.getSnapshot(), 'invalid');

    now += 1;
    tracker.setJointState(jointState(0.1, {
      receivedAtMs: now,
      stamp: { sec: 11, nanosec: 0 },
    }));
    assert.equal(tracker.getSnapshot().state, 'live');
    tracker.dispose();
  });
});
