/**
 * Unit tests for OpenSim calibration status display helper (Phase 17).
 */
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { formatCalibrationStatus } from './calibrationStatus.js';
import type { OpenSimStatusSnapshot } from '../../types/health.js';

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
