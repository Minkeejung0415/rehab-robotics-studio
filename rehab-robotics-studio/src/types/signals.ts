/**
 * Signal & sample data models.
 *
 * These describe the *payloads* that flow through the graph. Today they are
 * produced by `MockDataSource`; later the same shapes will be produced by a
 * `RosbridgeDataSource` / Red Pitaya adapter without any consumer changes.
 */

/** The set of typed wires the visual language understands. */
export type SignalType =
  | 'number'
  | 'bool'
  | 'event'
  | 'force3d'
  | 'emg_signal'
  | 'imu'
  | 'motor_state'
  | 'joint_state'
  | 'system_status';

/** 3-axis force / torque sample (load cell). Units: Newtons. */
export interface ForceData {
  fx: number;
  fy: number;
  fz: number;
  /** Resultant magnitude, convenience field. */
  mag: number;
  /** Sample timestamp, seconds. */
  t: number;
}

/** Single-channel EMG sample. Units: millivolts. */
export interface EmgData {
  /** Raw signed sample. */
  raw: number;
  /** Rectified + smoothed envelope. */
  envelope: number;
  channel: number;
  t: number;
}

/** Inertial measurement sample. */
export interface ImuData {
  /** Orientation quaternion [w, x, y, z]. */
  quat: [number, number, number, number];
  /** Linear acceleration [x, y, z], m/s^2. */
  accel: [number, number, number];
  /** Angular velocity [x, y, z], rad/s. */
  gyro: [number, number, number];
  t: number;
}

/** Motor / actuator feedback. */
export interface MotorState {
  /** Position, rad. */
  position: number;
  /** Velocity, rad/s. */
  velocity: number;
  /** Torque, Nm. */
  torque: number;
  /** Current, A. */
  current: number;
  /** Winding temperature, deg C. */
  temperature: number;
  enabled: boolean;
  fault: boolean;
  t: number;
}

/**
 * One acquisition frame: the bundle a DataSource emits per tick. A real source
 * would populate these from hardware; the mock synthesises them.
 */
export interface Frame {
  /** Frame timestamp, seconds (wall-clock-ish). */
  t: number;
  force: ForceData;
  emg: EmgData;
  imu: ImuData;
  motor: MotorState;
  /**
   * Deprecated optional field: custom relative-quat degrees from
   * `/opensim/joint_angle`. Not used by the product knee path; future IK uses
   * calibrated `/opensim/joint_states`.
   */
  jointAngleDeg?: number;
  /**
   * Official, fail-closed OpenSim IK knee angle from `/opensim/joint_states`.
   * `null` means the calibrated/valid/fresh product gate is closed.
   */
  openSimKneeAngleDeg?: number | null;
}

/** Stable, bounded reasons for rejecting an untrusted canonical envelope. */
export type CanonicalSignalRejectionReason =
  | 'schema_invalid'
  | 'device_id_invalid'
  | 'topic_device_mismatch'
  | 'sequence_invalid'
  | 'sequence_origin_invalid'
  | 'acquisition_time_invalid'
  | 'bridge_time_invalid'
  | 'reconnect_epoch_invalid'
  | 'mapping_epoch_invalid'
  | 'capability_invalid'
  | 'raw_field_missing'
  | 'raw_field_invalid'
  | 'raw_field_out_of_range'
  | 'conversion_invalid'
  | 'quaternion_invalid'
  | 'applied_mapping_invalid';

export type SignalAvailabilityReason =
  | 'capability_absent'
  | 'config_invalid'
  | 'calibration_missing'
  | 'calibration_invalid'
  | 'stale'
  | 'missing'
  | 'malformed'
  | 'non_finite'
  | 'zero_norm'
  | 'norm_out_of_range';

export type ReadonlyVector3 = readonly [number, number, number];
export type ReadonlyQuaternion = readonly [number, number, number, number];

export interface CanonicalTiming {
  readonly sequence: number;
  readonly sequence_origin: 'device' | 'bridge_session';
  readonly acquisition_time_us: number | null;
  readonly acquisition_clock: string | null;
  readonly bridge_monotonic_time_us: number;
}

export interface CanonicalEpochs {
  readonly reconnect_epoch: number;
  readonly mapping_epoch: number;
}

export interface CanonicalCapabilities {
  readonly accel: boolean;
  readonly gyro: boolean;
  readonly magnetometer: boolean;
  readonly quaternion: boolean;
}

export interface CanonicalRawChannels {
  readonly ax: number;
  readonly ay: number;
  readonly az: number;
  readonly gx: number;
  readonly gy: number;
  readonly gz: number;
  readonly mx: number;
  readonly my: number;
  readonly mz: number;
}

export type CanonicalVectorAvailability<Unit extends string> =
  | {
      readonly available: true;
      readonly unit: Unit;
      readonly values: Readonly<{ x: number; y: number; z: number }>;
    }
  | { readonly available: false; readonly reason: SignalAvailabilityReason };

export type CanonicalQuaternionAvailability =
  | { readonly available: true; readonly values: ReadonlyQuaternion }
  | { readonly available: false; readonly reason: SignalAvailabilityReason };

export interface CanonicalConversions {
  readonly accel: CanonicalVectorAvailability<'m/s^2'>;
  readonly gyro: CanonicalVectorAvailability<'rad/s'>;
  readonly magnetometer: CanonicalVectorAvailability<'µT'>;
}

export interface CanonicalAppliedMapping {
  readonly revision: number;
  readonly segment: string | null;
  readonly frame: string | null;
  readonly model_hash: string;
}

/** Browser-owned, immutable value produced only by the strict canonical parser. */
export interface CanonicalSignalSample extends CanonicalTiming, CanonicalEpochs {
  readonly schema: 'rehab.signal_sample.1';
  readonly device_id: `esp32:${string}`;
  readonly topic_token: `mac_${string}`;
  readonly capabilities: CanonicalCapabilities;
  readonly raw: CanonicalRawChannels;
  readonly raw_units: 'counts';
  readonly si: CanonicalConversions;
  readonly quaternion: CanonicalQuaternionAvailability;
  readonly applied_mapping: CanonicalAppliedMapping;
}

export type CanonicalSignalParseResult =
  | { readonly ok: true; readonly value: CanonicalSignalSample }
  | { readonly ok: false; readonly reason: CanonicalSignalRejectionReason | 'canonical_parser_unimplemented' };
