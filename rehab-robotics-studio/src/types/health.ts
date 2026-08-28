/** Typed UI snapshots for ROS, OpenSim, recording, and fleet health payloads. */
export type RecordingHealth = {
  state?: string;
  session_id?: string | null;
  error?: string | null;
  sd_ready?: number | null;
  saved_samples?: number | null;
  file_byte_size?: number | null;
  file_checksum?: string | null;
  checksum_type?: string | null;
  finalization_reason?: string | null;
};

export type EspHealthSnapshot = {
  schema?: string;
  node_id?: string;
  connection_state?: string;
  reconnect_count?: number;
  configured_rate_hz?: number;
  effective_rate_hz?: number;
  observed_stream_rate_hz?: number;
  last_frame_age_ms?: number | null;
  frames_received?: number;
  recording?: RecordingHealth;
};

export type PairHealthSnapshot = {
  schema?: string;
  pair_available?: boolean;
  master?: EspHealthSnapshot;
  slave?: EspHealthSnapshot | null;
};

export type OpenSimSensorHealth = {
  state?: string;
  updates?: number;
  age_s?: number | null;
  last_error?: string;
};

export type OpenSimStatusSnapshot = {
  schema?: string;
  sensors?: {
    master?: OpenSimSensorHealth;
    slave?: OpenSimSensorHealth;
  };
  visualization?: {
    available?: boolean;
    state?: string;
    reason?: string;
    model_path?: string;
  };
  /** Phase 17 reference-pose calibration status from opensim_bridge. */
  calibration?: {
    state?: string;
    reason?: string;
    known_pose?: string;
    sample_count?: number;
    window_s?: number;
    calibration_id?: string | null;
    has_offsets?: boolean;
  };
  /**
   * Deprecated status field from optional debug Float64 publisher.
   * Do not present as product OpenSim IK — use waiting/calibration UX instead.
   */
  joint_angle_deg?: number | null;
};

/** ROS 2 builtin_interfaces/Time represented without unsafe nanosecond arithmetic. */
export type RosStamp = {
  sec: number;
  nanosec: number;
};

/** Rosbridge-friendly `/opensim/ik_status` payload. */
export type OpenSimIkStatusSnapshot = {
  schema?: string;
  solution_valid?: boolean;
  reason?: string;
  calibration_id?: string | null;
  orientation_residual_rms?: number | null;
  orientation_residual_max?: number | null;
  input_age_s?: number | null;
  backend?: string;
};

/** Validated `/opensim/joint_states` data at the frontend transport boundary. */
export type OpenSimJointStateSnapshot = {
  stamp: RosStamp;
  names: readonly string[];
  positions: readonly number[];
  /** Local monotonic receipt time. Never compare this with the ROS source clock. */
  receivedAtMs: number;
};

/** Ephemeral browser request state; backend visualization status remains authoritative. */
export type OpenSimVisualizerRequestSnapshot =
  | { state: 'idle'; reason: '' }
  | { state: 'opening'; reason: '' }
  | { state: 'failed'; reason: string };

export type LiveKneeAngleSnapshot =
  | {
      state: 'live';
      valueDeg: number;
      reason: '';
      sourceStamp: RosStamp;
      receivedAtMs: number;
    }
  | {
      state: 'waiting' | 'invalid' | 'stale';
      valueDeg: null;
      reason: string;
    };
