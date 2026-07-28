/**
 * Unit tests for OpenSim calibration status display helper (Phase 17).
 */
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { formatCalibrationStatus } from './calibrationStatus.js';
import { formatOpenSimHealth } from './HealthPanel.js';
import type {
  LiveKneeAngleSnapshot,
  OpenSimStatusSnapshot,
} from '../../types/health.js';

const waitingAngle: LiveKneeAngleSnapshot = {
  state: 'waiting',
  valueDeg: null,
  reason: 'Waiting for calibrated IK',
};

describe('formatCalibrationStatus', () => {
  it('defaults to UNCALIBRATED when snapshot missing', () => {
    const result = formatCalibrationStatus(null);
    assert.equal(result.state, 'UNCALIBRATED');
    assert.equal(result.reason, '');
  });

  it('surfaces CAPTURING / CALIBRATED / FAILED and reason', () => {
    for (const state of ['UNCALIBRATED', 'CAPTURING', 'CALIBRATED', 'FAILED'] as const) {
      const snapshot: OpenSimStatusSnapshot = {
        calibration: { state, reason: state === 'FAILED' ? 'stability/dispersion exceeded' : '' },
      };
      const result = formatCalibrationStatus(snapshot);
      assert.equal(result.state, state);
      if (state === 'FAILED') {
        assert.match(result.reason, /dispersion/i);
      }
    }
  });
});

describe('formatOpenSimHealth', () => {
  it('keeps calibration, IK, angle freshness, and visualizer truth separate', () => {
    const view = formatOpenSimHealth(
      {
        calibration: {
          state: 'CALIBRATED',
          reason: '',
          calibration_id: 'cal-42',
        },
        visualization: {
          available: true,
          state: 'open',
          reason: '',
          model_path: '/models/gait2392.osim',
        },
      },
      {
        solution_valid: true,
        reason: '',
        calibration_id: 'cal-42',
        input_age_s: 0.125,
      },
      {
        state: 'live',
        valueDeg: 90,
        reason: '',
        sourceStamp: { sec: 12, nanosec: 3 },
        receivedAtMs: 100,
      },
      { state: 'idle', reason: '' },
    );

    assert.equal(view.calibrationState, 'CALIBRATED');
    assert.equal(view.calibrationReason, '—');
    assert.equal(view.ikSolution, 'Valid');
    assert.equal(view.ikInputAge, '0.13 s');
    assert.equal(view.calibrationId, 'cal-42');
    assert.equal(view.kneeAngle, '90.0 deg');
    assert.equal(view.model, '/models/gait2392.osim');
    assert.equal(view.visualizer, 'Open');
    assert.equal(view.visualizerTone, 'ok');
  });

  it('normalizes invalid and unavailable reasons without exposing raw payloads', () => {
    const view = formatOpenSimHealth(
      {
        calibration: {
          state: 'FAILED',
          reason: 'capture_dispersion_exceeded',
        },
        visualization: {
          available: false,
          state: 'unavailable',
          reason: '[object Object]',
        },
      },
      {
        solution_valid: false,
        reason: 'calibration_id_mismatch',
        input_age_s: null,
      },
      waitingAngle,
      { state: 'idle', reason: '' },
    );

    assert.equal(view.calibrationReason, 'Capture dispersion exceeded');
    assert.equal(view.ikSolution, 'Invalid — Calibration id mismatch');
    assert.equal(view.ikInputAge, '—');
    assert.equal(
      view.visualizer,
      'Unavailable — OpenSim visualizer is unavailable',
    );
    assert.equal(view.visualizerTone, 'fault');
    assert.doesNotMatch(JSON.stringify(view), /\[object Object\]/);
  });

  it('retains a failed request through unavailable status and replaces it on backend recovery', () => {
    const unavailable: OpenSimStatusSnapshot = {
      calibration: { state: 'UNCALIBRATED', reason: '' },
      visualization: {
        available: false,
        state: 'unavailable',
        reason: 'native_runtime_missing',
      },
    };
    const failed = formatOpenSimHealth(
      unavailable,
      null,
      waitingAngle,
      { state: 'failed', reason: 'trigger_timeout' },
    );
    assert.equal(failed.visualizer, 'Failed — Trigger timeout');

    const opening = formatOpenSimHealth(
      {
        ...unavailable,
        visualization: {
          available: true,
          state: 'opening',
          reason: '',
        },
      },
      null,
      waitingAngle,
      { state: 'failed', reason: 'trigger_timeout' },
    );
    assert.equal(opening.visualizer, 'Opening…');

    const open = formatOpenSimHealth(
      {
        ...unavailable,
        visualization: {
          available: true,
          state: 'open',
          reason: '',
        },
      },
      null,
      waitingAngle,
      { state: 'idle', reason: '' },
    );
    assert.equal(open.visualizer, 'Open');
  });

  it('shows request opening and stale angle as independent attention states', () => {
    const view = formatOpenSimHealth(
      null,
      null,
      {
        state: 'stale',
        valueDeg: null,
        reason: 'JointState stale - no fresh angle for 2.0 s',
      },
      { state: 'opening', reason: '' },
    );
    assert.equal(view.kneeAngle, 'Stale');
    assert.equal(view.visualizer, 'Opening…');
    assert.equal(view.visualizerTone, 'attention');
  });
});
