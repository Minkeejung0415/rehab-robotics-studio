/**
 * Canonical TypeScript measurement contract for ESP32 ICM-20948 range-to-SI conversion.
 *
 * Pure module — no React, Zustand, or DOM imports.
 *
 * Exports:
 *   SensorConfig            - Wire-format sensor config shape
 *   GRAVITY                 - Standard gravity (m/s² per g)
 *   DEG_TO_RAD              - Degree-to-radian conversion
 *   ACCEL_LSB_PER_G         - Accelerometer sensitivities by range (count/g)
 *   GYRO_LSB_PER_DPS        - Gyroscope sensitivities by range (count/(deg/s))
 *   ValidateResult<T>       - Discriminated union for validation results
 *   validateSensorConfig()  - Strictly validate an inbound sensor_config object
 *   accelCountToMps2()      - Convert a raw count to m/s² using a config snapshot
 *   gyroCountToRad_s()      - Convert a raw count to rad/s using a config snapshot
 *
 * Range tables match Python measurement_contract.py and firmware kAccLsbPerG /
 * kGyrLsbPerDps in step_node.ino / step_node_slave.ino exactly.
 */

// ── Physical constants ────────────────────────────────────────────────────────

export const GRAVITY = 9.80665;          // m/s² per g  (BIPM / ISO 80000-3)
export const DEG_TO_RAD = Math.PI / 180;

// ── ICM-20948 full-scale range sensitivity tables ─────────────────────────────
// Keys are the range label used in ROS parameters and the wire sensor_config.
// Values are the LSB-per-unit sensitivity at that range preset.
// Matches Python: ACCEL_LSB_PER_G = {2:16384, 4:8192, 8:4096, 16:2048}
//                 GYRO_LSB_PER_DPS = {250:131.072, 500:65.536, 1000:32.768, 2000:16.384}

export const ACCEL_LSB_PER_G: Readonly<Record<number, number>> = {
  2:  16384,
  4:   8192,
  8:   4096,
  16:  2048,
};

export const GYRO_LSB_PER_DPS: Readonly<Record<number, number>> = {
  250:  131.072,
  500:   65.536,
  1000:  32.768,
  2000:  16.384,
};

// ── Wire-format sensor config type ────────────────────────────────────────────

export type SensorConfig = {
  accel_range_g: number;
  gyro_range_dps: number;
  accel_lsb_per_g: number;
  gyro_lsb_per_dps: number;
  units: Record<string, string>;
};

// ── Validation result discriminated union ─────────────────────────────────────

export type ValidateResult<T> =
  | { ok: true; value: T }
  | { ok: false; reason: string };

// ── Strict inbound validator ──────────────────────────────────────────────────

/**
 * Strictly validate an inbound sensor_config object.
 *
 * Never throws — always returns a ValidateResult. On failure, the reason
 * field describes the first violation found. On success, returns the typed
 * SensorConfig value.
 *
 * Checks performed (in order):
 *   1. raw must be a non-null object
 *   2. All required keys must be present
 *   3. accel_range_g must be in [2, 4, 8, 16]
 *   4. gyro_range_dps must be in [250, 500, 1000, 2000]
 *   5. accel_lsb_per_g must be finite and positive
 *   6. gyro_lsb_per_dps must be finite and positive
 *   7. accel_lsb_per_g must be consistent with canonical table value (rtol 1e-9)
 *   8. gyro_lsb_per_dps must be consistent with canonical table value (rtol 1e-9)
 *   9. units must be a non-null object with a 'raw' key
 */
export function validateSensorConfig(raw: unknown): ValidateResult<SensorConfig> {
  // Check 1: must be a non-null object
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) {
    return { ok: false, reason: `sensor_config must be a non-null object, got ${raw === null ? 'null' : typeof raw}` };
  }

  const obj = raw as Record<string, unknown>;

  // Check 2: all required keys must be present
  const requiredKeys = ['accel_range_g', 'gyro_range_dps', 'accel_lsb_per_g', 'gyro_lsb_per_dps', 'units'];
  for (const key of requiredKeys) {
    if (!(key in obj)) {
      return { ok: false, reason: `sensor_config is missing required key: '${key}'` };
    }
  }

  const accelRangeG = obj['accel_range_g'] as number;
  const gyroRangeDps = obj['gyro_range_dps'] as number;
  const accelLsb = obj['accel_lsb_per_g'] as number;
  const gyroLsb = obj['gyro_lsb_per_dps'] as number;
  const units = obj['units'];

  // Check 3: accel_range_g must be a supported value
  if (!(accelRangeG in ACCEL_LSB_PER_G)) {
    return { ok: false, reason: `sensor_config accel_range_g ${String(accelRangeG)} is not supported; must be one of [2, 4, 8, 16]` };
  }

  // Check 4: gyro_range_dps must be a supported value
  if (!(gyroRangeDps in GYRO_LSB_PER_DPS)) {
    return { ok: false, reason: `sensor_config gyro_range_dps ${String(gyroRangeDps)} is not supported; must be one of [250, 500, 1000, 2000]` };
  }

  // Check 5: accel_lsb_per_g must be finite and positive
  if (typeof accelLsb !== 'number' || !Number.isFinite(accelLsb) || accelLsb <= 0) {
    return { ok: false, reason: `sensor_config accel_lsb_per_g must be a finite positive number, got ${String(accelLsb)}` };
  }

  // Check 6: gyro_lsb_per_dps must be finite and positive
  if (typeof gyroLsb !== 'number' || !Number.isFinite(gyroLsb) || gyroLsb <= 0) {
    return { ok: false, reason: `sensor_config gyro_lsb_per_dps must be a finite positive number, got ${String(gyroLsb)}` };
  }

  // Check 7: accel_lsb_per_g must be consistent with canonical table (rtol 1e-9)
  const expectedAccelLsb = ACCEL_LSB_PER_G[accelRangeG];
  if (Math.abs(accelLsb - expectedAccelLsb) / expectedAccelLsb > 1e-9) {
    return {
      ok: false,
      reason: `sensor_config accel_lsb_per_g ${String(accelLsb)} is inconsistent with canonical value ${String(expectedAccelLsb)} for accel_range_g=${String(accelRangeG)}`,
    };
  }

  // Check 8: gyro_lsb_per_dps must be consistent with canonical table (rtol 1e-9)
  const expectedGyroLsb = GYRO_LSB_PER_DPS[gyroRangeDps];
  if (Math.abs(gyroLsb - expectedGyroLsb) / expectedGyroLsb > 1e-9) {
    return {
      ok: false,
      reason: `sensor_config gyro_lsb_per_dps ${String(gyroLsb)} is inconsistent with canonical value ${String(expectedGyroLsb)} for gyro_range_dps=${String(gyroRangeDps)}`,
    };
  }

  // Check 9: units must be a non-null object with a 'raw' key
  if (units === null || typeof units !== 'object' || Array.isArray(units)) {
    return { ok: false, reason: "sensor_config units must be a non-null object" };
  }
  if (!('raw' in (units as Record<string, unknown>))) {
    return { ok: false, reason: "sensor_config units must contain at least a 'raw' key" };
  }

  return {
    ok: true,
    value: {
      accel_range_g: accelRangeG,
      gyro_range_dps: gyroRangeDps,
      accel_lsb_per_g: accelLsb,
      gyro_lsb_per_dps: gyroLsb,
      units: units as Record<string, string>,
    },
  };
}

// ── SI conversion helpers ─────────────────────────────────────────────────────

/**
 * Convert a raw accelerometer count to m/s² using the config snapshot.
 * Returns count / config.accel_lsb_per_g * GRAVITY
 */
export function accelCountToMps2(count: number, config: SensorConfig): number {
  return count / config.accel_lsb_per_g * GRAVITY;
}

/**
 * Convert a raw gyroscope count to rad/s using the config snapshot.
 * Returns count / config.gyro_lsb_per_dps * DEG_TO_RAD
 */
export function gyroCountToRad_s(count: number, config: SensorConfig): number {
  return count / config.gyro_lsb_per_dps * DEG_TO_RAD;
}
