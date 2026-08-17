/**
 * 09-02-01: Shared-fixture table tests and rejection partitions for measurementContract.ts
 *
 * Tests:
 *   - All 32 shared-fixture cases pass to 1e-9 tolerance
 *   - validateSensorConfig accepts a canonical round-trip object
 *   - validateSensorConfig rejects each of 10 required rejection partitions
 */

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  ACCEL_LSB_PER_G,
  GYRO_LSB_PER_DPS,
  validateSensorConfig,
  accelCountToMps2,
  gyroCountToRad_s,
  magnetometerCountsToUT,
  type SensorConfig,
} from './measurementContract.js';

// ── Load shared fixture ───────────────────────────────────────────────────────

const casesPath = join(
  dirname(fileURLToPath(import.meta.url)),
  '../../../backend/test/fixtures/measurement_contract_cases.json',
);

type FixtureCase = {
  role: string;
  raw_count: number;
  accel_range_g: number;
  gyro_range_dps: number;
  expected_accel_mps2: number;
  expected_gyro_rad_s: number;
};

const cases: FixtureCase[] = JSON.parse(readFileSync(casesPath, 'utf-8')) as FixtureCase[];

const signalCasesPath = join(
  dirname(fileURLToPath(import.meta.url)),
  '../../../backend/test/fixtures/signal_contract_cases.json',
);
type SignalMeasurementCase = {
  id: string;
  accel_range_g?: number;
  gyro_range_dps?: number;
  raw?: number | [number, number, number];
  expected_accel_mps2?: number;
  expected_gyro_rad_s?: number;
  sensitivity_uT_per_count?: number;
  calibration?: Record<string, unknown>;
  expected_uT?: [number, number, number];
  reason?: string;
};
const signalMeasurementCases = (
  JSON.parse(readFileSync(signalCasesPath, 'utf-8')) as { measurement_cases: SignalMeasurementCase[] }
).measurement_cases;

// ── Helper: build a canonical SensorConfig ─────────────────────────────────────

function makeConfig(accelRangeG: number, gyroRangeDps: number): SensorConfig {
  return {
    accel_range_g: accelRangeG,
    gyro_range_dps: gyroRangeDps,
    accel_lsb_per_g: ACCEL_LSB_PER_G[accelRangeG],
    gyro_lsb_per_dps: GYRO_LSB_PER_DPS[gyroRangeDps],
    units: { raw: 'count' },
  };
}

// ── Helper: build a canonical wire-format sensor_config object ─────────────────

function makeWireConfig(accelRangeG: number, gyroRangeDps: number): Record<string, unknown> {
  return {
    accel_range_g: accelRangeG,
    gyro_range_dps: gyroRangeDps,
    accel_lsb_per_g: ACCEL_LSB_PER_G[accelRangeG],
    gyro_lsb_per_dps: GYRO_LSB_PER_DPS[gyroRangeDps],
    units: { raw: 'count' },
  };
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('measurementContract — 09-02-01', () => {

  it('09-02-01 all 32 shared-fixture cases match expected SI values', () => {
    assert.equal(cases.length, 32, `Expected 32 fixture cases, got ${cases.length}`);

    for (const c of cases) {
      const config = makeConfig(c.accel_range_g, c.gyro_range_dps);

      const gotAccel = accelCountToMps2(c.raw_count, config);
      const accelDiff = Math.abs(gotAccel - c.expected_accel_mps2);
      assert.ok(
        accelDiff < 1e-9,
        `accelCountToMps2 for role=${c.role} accel_range_g=${c.accel_range_g}: ` +
          `got ${gotAccel}, expected ${c.expected_accel_mps2}, diff=${accelDiff}`,
      );

      const gotGyro = gyroCountToRad_s(c.raw_count, config);
      const gyroDiff = Math.abs(gotGyro - c.expected_gyro_rad_s);
      assert.ok(
        gyroDiff < 1e-9,
        `gyroCountToRad_s for role=${c.role} gyro_range_dps=${c.gyro_range_dps}: ` +
          `got ${gotGyro}, expected ${c.expected_gyro_rad_s}, diff=${gyroDiff}`,
      );
    }
  });

  it('09-02-01 validateSensorConfig accepts a canonical round-trip object', () => {
    // Canonical config for 8g / 2000dps
    const wire = makeWireConfig(8, 2000);
    const result = validateSensorConfig(wire);
    assert.equal(result.ok, true, `Expected ok=true, got reason: ${!result.ok ? result.reason : ''}`);
    if (result.ok) {
      assert.equal(result.value.accel_range_g, 8);
      assert.equal(result.value.gyro_range_dps, 2000);
      assert.equal(result.value.accel_lsb_per_g, ACCEL_LSB_PER_G[8]);
      assert.equal(result.value.gyro_lsb_per_dps, GYRO_LSB_PER_DPS[2000]);
    }
  });

  it('09-02-01 validateSensorConfig rejects each required rejection partition', () => {

    // Partition 1: null
    assert.equal(validateSensorConfig(null).ok, false, 'null must be rejected');

    // Partition 2: empty object (missing all fields)
    assert.equal(validateSensorConfig({}).ok, false, '{} (missing all fields) must be rejected');

    // Partition 3: unsupported accel_range_g (3 is not in [2,4,8,16])
    assert.equal(
      validateSensorConfig({
        accel_range_g: 3,
        gyro_range_dps: 250,
        accel_lsb_per_g: 16384,
        gyro_lsb_per_dps: 131.072,
        units: { raw: 'count' },
      }).ok,
      false,
      'accel_range_g=3 must be rejected (unsupported)',
    );

    // Partition 4: unsupported gyro_range_dps (42 is not in [250,500,1000,2000])
    assert.equal(
      validateSensorConfig({
        accel_range_g: 2,
        gyro_range_dps: 42,
        accel_lsb_per_g: 16384,
        gyro_lsb_per_dps: 131.072,
        units: { raw: 'count' },
      }).ok,
      false,
      'gyro_range_dps=42 must be rejected (unsupported)',
    );

    // Partition 5: accel_lsb_per_g = 0
    assert.equal(
      validateSensorConfig({
        accel_range_g: 2,
        gyro_range_dps: 250,
        accel_lsb_per_g: 0,
        gyro_lsb_per_dps: 131.072,
        units: { raw: 'count' },
      }).ok,
      false,
      'accel_lsb_per_g=0 must be rejected (not positive)',
    );

    // Partition 6: accel_lsb_per_g = NaN (JSON transmits as null or invalid; test with NaN directly)
    assert.equal(
      validateSensorConfig({
        accel_range_g: 2,
        gyro_range_dps: 250,
        accel_lsb_per_g: NaN,
        gyro_lsb_per_dps: 131.072,
        units: { raw: 'count' },
      }).ok,
      false,
      'accel_lsb_per_g=NaN must be rejected (not finite)',
    );

    // Partition 7: accel_lsb_per_g = Infinity
    assert.equal(
      validateSensorConfig({
        accel_range_g: 2,
        gyro_range_dps: 250,
        accel_lsb_per_g: Infinity,
        gyro_lsb_per_dps: 131.072,
        units: { raw: 'count' },
      }).ok,
      false,
      'accel_lsb_per_g=Infinity must be rejected (not finite)',
    );

    // Partition 8: range/sensitivity mismatch (accel_range_g=8 but accel_lsb_per_g=16384 which is 2g sensitivity)
    assert.equal(
      validateSensorConfig({
        accel_range_g: 8,
        gyro_range_dps: 250,
        accel_lsb_per_g: 16384,   // 2g sensitivity, not 8g (4096)
        gyro_lsb_per_dps: 131.072,
        units: { raw: 'count' },
      }).ok,
      false,
      'accel_range_g=8 with accel_lsb_per_g=16384 must be rejected (range/sensitivity mismatch)',
    );

    // Partition 9: missing 'units' key entirely
    assert.equal(
      validateSensorConfig({
        accel_range_g: 2,
        gyro_range_dps: 250,
        accel_lsb_per_g: 16384,
        gyro_lsb_per_dps: 131.072,
        // units missing
      }).ok,
      false,
      'missing units key must be rejected',
    );

    // Partition 10: units present but missing 'raw' key
    assert.equal(
      validateSensorConfig({
        accel_range_g: 2,
        gyro_range_dps: 250,
        accel_lsb_per_g: 16384,
        gyro_lsb_per_dps: 131.072,
        units: { accel_range: 'g' },  // 'raw' key absent
      }).ok,
      false,
      "units without 'raw' key must be rejected",
    );
  });

});

describe('measurementContract — canonical signal fixture parity', () => {
  it('matches the shared deterministic accel and gyro conversion', () => {
    const c = signalMeasurementCases.find((entry) => entry.id === 'accel_gyro_valid');
    assert.ok(c && typeof c.raw === 'number');
    const config = makeConfig(c.accel_range_g!, c.gyro_range_dps!);
    assert.ok(Math.abs(accelCountToMps2(c.raw, config) - c.expected_accel_mps2!) < 1e-9);
    assert.ok(Math.abs(gyroCountToRad_s(c.raw, config) - c.expected_gyro_rad_s!) < 1e-9);
  });

  it('retains raw access and returns calibration_invalid for malformed provenance', () => {
    const c = signalMeasurementCases.find((entry) => entry.id === 'mag_calibration_invalid');
    assert.ok(c);
    const wire = makeWireConfig(2, 250);
    wire.magnetometer = {
      sensitivity_uT_per_count: 0.15,
      calibration: c.calibration,
    };
    const validated = validateSensorConfig(wire);
    assert.equal(validated.ok, true);
    if (!validated.ok) return;
    assert.equal(validated.value.magnetometer_availability, c.reason);
    assert.deepEqual(magnetometerCountsToUT([10, 20, -30], validated.value), {
      ok: false,
      reason: c.reason,
    });
  });

  it('requires calibration in addition to sensitivity before exposing microtesla', () => {
    const wire = makeWireConfig(2, 250);
    wire.magnetometer = { sensitivity_uT_per_count: 0.15, calibration: null };
    const validated = validateSensorConfig(wire);
    assert.equal(validated.ok, true);
    if (!validated.ok) return;
    assert.equal(validated.value.magnetometer_availability, 'calibration_missing');
    assert.deepEqual(magnetometerCountsToUT([10, 20, -30], validated.value), {
      ok: false,
      reason: 'calibration_missing',
    });
  });

  it('matches the shared calibrated magnetometer conversion', () => {
    const c = signalMeasurementCases.find((entry) => entry.id === 'mag_calibrated');
    assert.ok(c && Array.isArray(c.raw));
    const wire = makeWireConfig(2, 250);
    wire.magnetometer = {
      sensitivity_uT_per_count: c.sensitivity_uT_per_count,
      calibration: c.calibration,
    };
    const validated = validateSensorConfig(wire);
    assert.equal(validated.ok, true);
    if (!validated.ok) return;
    const converted = magnetometerCountsToUT(c.raw, validated.value);
    assert.equal(converted.ok, true);
    if (!converted.ok) return;
    converted.value.forEach((value, index) => {
      assert.ok(Math.abs(value - c.expected_uT![index]) < 1e-9);
    });
  });
});
