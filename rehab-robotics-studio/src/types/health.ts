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
  /**
   * Deprecated status field from optional debug Float64 publisher.
   * Do not present as product OpenSim IK — use waiting/calibration UX instead.
   */
  joint_angle_deg?: number | null;
};
