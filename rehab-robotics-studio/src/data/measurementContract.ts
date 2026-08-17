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
  magnetometer_sensitivity_uT_per_count?: number | null;
  magnetometer_calibration?: MagnetometerCalibration | null;
  magnetometer_availability?: MagnetometerAvailability;
};

export type MagnetometerAvailability = 'available' | 'calibration_missing' | 'calibration_invalid';

export type MagnetometerCalibration = {
  readonly schema: 'rehab.mag_calibration.1';
  readonly sensor_model: string;
  readonly axis_convention: 'xyz';
  readonly calibration_id: string;
  readonly calibration_hash: string;
  readonly hard_iron_uT: readonly [number, number, number];
  readonly soft_iron: readonly [
    readonly [number, number, number],
    readonly [number, number, number],
    readonly [number, number, number],
  ];
};

// ── Validation result discriminated union ─────────────────────────────────────

export type ValidateResult<T> =
  | { ok: true; value: T }
  | { ok: false; reason: string };

const CALIBRATION_KEYS = [
  'schema', 'sensor_model', 'axis_convention', 'calibration_id',
  'calibration_hash', 'hard_iron_uT', 'soft_iron',
] as const;
const CALIBRATION_HASH = /^sha256:[0-9a-f]{16,64}$/;
const MAX_PROVENANCE_TEXT = 64;

function finiteVector(value: unknown): [number, number, number] | null {
  if (!Array.isArray(value) || value.length !== 3) return null;
  if (value.some((entry) => typeof entry !== 'number' || !Number.isFinite(entry))) return null;
  return [value[0] as number, value[1] as number, value[2] as number];
}

export function validateMagnetometerCalibration(
  raw: unknown,
): ValidateResult<MagnetometerCalibration> {
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) {
    return { ok: false, reason: 'calibration_invalid' };
  }
  const obj = raw as Record<string, unknown>;
  const keys = Object.keys(obj).sort();
  if (keys.length !== CALIBRATION_KEYS.length
      || CALIBRATION_KEYS.some((key) => !Object.prototype.hasOwnProperty.call(obj, key))) {
    return { ok: false, reason: 'calibration_invalid' };
  }
  const boundedText = (value: unknown): value is string =>
    typeof value === 'string' && value.length > 0 && value.length <= MAX_PROVENANCE_TEXT;
  if (obj.schema !== 'rehab.mag_calibration.1'
      || !boundedText(obj.sensor_model)
      || obj.axis_convention !== 'xyz'
      || !boundedText(obj.calibration_id)
      || typeof obj.calibration_hash !== 'string'
      || !CALIBRATION_HASH.test(obj.calibration_hash)) {
    return { ok: false, reason: 'calibration_invalid' };
  }
  const hardIron = finiteVector(obj.hard_iron_uT);
  if (!hardIron || !Array.isArray(obj.soft_iron) || obj.soft_iron.length !== 3) {
    return { ok: false, reason: 'calibration_invalid' };
  }
  const rows = obj.soft_iron.map(finiteVector);
  if (rows.some((row) => row === null)) return { ok: false, reason: 'calibration_invalid' };
  return {
    ok: true,
    value: {
      schema: 'rehab.mag_calibration.1',
      sensor_model: obj.sensor_model,
      axis_convention: 'xyz',
      calibration_id: obj.calibration_id,
      calibration_hash: obj.calibration_hash,
      hard_iron_uT: hardIron,
      soft_iron: [rows[0]!, rows[1]!, rows[2]!],
    },
  };
}

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
    if (!Object.prototype.hasOwnProperty.call(obj, key)) {
      return { ok: false, reason: `sensor_config is missing required key: '${key}'` };
    }
  }

  const accelRangeG = obj['accel_range_g'];
  const gyroRangeDps = obj['gyro_range_dps'];
  const accelLsb = obj['accel_lsb_per_g'] as number;
  const gyroLsb = obj['gyro_lsb_per_dps'] as number;
  const units = obj['units'];

  // Check 3: accel_range_g must be a supported value
  if (typeof accelRangeG !== 'number' || !Number.isInteger(accelRangeG)
      || !Object.prototype.hasOwnProperty.call(ACCEL_LSB_PER_G, accelRangeG)) {
    return { ok: false, reason: `sensor_config accel_range_g ${String(accelRangeG)} is not supported; must be one of [2, 4, 8, 16]` };
  }

  // Check 4: gyro_range_dps must be a supported value
  if (typeof gyroRangeDps !== 'number' || !Number.isInteger(gyroRangeDps)
      || !Object.prototype.hasOwnProperty.call(GYRO_LSB_PER_DPS, gyroRangeDps)) {
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
  if (!Object.prototype.hasOwnProperty.call(units, 'raw')) {
    return { ok: false, reason: "sensor_config units must contain at least a 'raw' key" };
  }

  let magnetometerSensitivity: number | null = null;
  let magnetometerCalibration: MagnetometerCalibration | null = null;
  let magnetometerAvailability: MagnetometerAvailability = 'calibration_missing';
  const magnetometer = obj['magnetometer'];
  if (magnetometer !== undefined && magnetometer !== null) {
    if (typeof magnetometer !== 'object' || Array.isArray(magnetometer)) {
      return { ok: false, reason: 'sensor_config magnetometer must be a dict' };
    }
    const mag = magnetometer as Record<string, unknown>;
    const sensitivity = mag.sensitivity_uT_per_count;
    const calibration = mag.calibration;
    if (typeof sensitivity !== 'number' || !Number.isFinite(sensitivity) || sensitivity <= 0) {
      magnetometerAvailability = 'calibration_invalid';
    } else {
      magnetometerSensitivity = sensitivity;
      if (calibration !== undefined && calibration !== null) {
        const validatedCalibration = validateMagnetometerCalibration(calibration);
        if (validatedCalibration.ok) {
          magnetometerCalibration = validatedCalibration.value;
          magnetometerAvailability = 'available';
        } else {
          magnetometerAvailability = 'calibration_invalid';
        }
      }
    }
  }

  return {
    ok: true,
    value: {
      accel_range_g: accelRangeG,
      gyro_range_dps: gyroRangeDps,
      accel_lsb_per_g: accelLsb,
      gyro_lsb_per_dps: gyroLsb,
      units: units as Record<string, string>,
      magnetometer_sensitivity_uT_per_count: magnetometerSensitivity,
      magnetometer_calibration: magnetometerCalibration,
      magnetometer_availability: magnetometerAvailability,
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

export function magnetometerCountsToUT(
  counts: readonly number[],
  config: SensorConfig,
): ValidateResult<readonly [number, number, number]> {
  const availability = config.magnetometer_availability ?? 'calibration_missing';
  const sensitivity = config.magnetometer_sensitivity_uT_per_count;
  const calibration = config.magnetometer_calibration;
  if (availability !== 'available' || sensitivity == null || calibration == null) {
    return { ok: false, reason: availability };
  }
  if (counts.length !== 3 || counts.some((count) => !Number.isInteger(count))) {
    return { ok: false, reason: 'raw_field_invalid' };
  }
  const centered: [number, number, number] = [
    counts[0]! * sensitivity - calibration.hard_iron_uT[0],
    counts[1]! * sensitivity - calibration.hard_iron_uT[1],
    counts[2]! * sensitivity - calibration.hard_iron_uT[2],
  ];
  const converted = calibration.soft_iron.map((row) =>
    row.reduce((sum, coefficient, index) => sum + coefficient * centered[index]!, 0),
  ) as [number, number, number];
  return { ok: true, value: converted };
}
