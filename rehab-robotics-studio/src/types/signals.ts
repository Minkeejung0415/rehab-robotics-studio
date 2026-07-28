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
