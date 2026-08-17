import type { DataSource, OpenSimDataSource } from './DataSource';
import type {
  CanonicalSignalRejectionReason,
  CanonicalSignalSample,
  Frame,
  ImuData,
} from '../types/signals';
import type {
  OpenSimIkStatusSnapshot,
  OpenSimJointStateSnapshot,
  OpenSimStatusSnapshot,
  PairHealthSnapshot,
} from '../types/health';
import type {
  ModelCatalogSnapshot,
  MappingCurrentSnapshot,
  FleetRegistrySnapshot,
  NCalibrationStatusSnapshot,
  InputValiditySnapshot,
} from '../state/mappingStore';
import { parseMappingCurrentSnapshot } from '../state/mappingStore';
import {
  isValidRosStamp,
  normalizeLiveKneeReason,
} from './liveKneeAngle';
import {
  validateSensorConfig,
  accelCountToMps2,
  gyroCountToRad_s,
  type SensorConfig,
} from './measurementContract';
import { parseCanonicalSignalSample } from './signalContract';

type RawEspMessage = {
  topic_schema?: string;
  time_us?: number;
  sensor_config?: unknown;
  imu?: Partial<Record<'ax' | 'ay' | 'az' | 'gx' | 'gy' | 'gz', number>>;
  quat?: Partial<Record<'qw' | 'qx' | 'qy' | 'qz', number>>;
};

type RosbridgeEnvelope = {
  op?: string;
  topic?: string;
  msg?: unknown;
  id?: string;
  values?: {
    success?: boolean;
    message?: string;
    results?: Array<{ successful?: boolean; reason?: string }>;
  };
};

export type RecordingCommandResult = { success: boolean; message: string };
export type ImuControlParameter =
  | 'sample_rate_hz'
  | 'effective_sample_rate_hz'
  | 'filter_enabled'
  | 'accel_range_g'
  | 'gyro_range_dps';

const DEFAULT_URL = 'ws://127.0.0.1:9090';
const DEFAULT_MASTER_TOPIC = '/esp/raw/master';
const DEFAULT_SLAVE_TOPIC = '/esp/raw/slave';
const DEFAULT_PAIR_HEALTH_TOPIC = '/esp/status/pair';
const DEFAULT_OPENSIM_STATUS_TOPIC = '/opensim/status';
const DEFAULT_OPENSIM_IK_STATUS_TOPIC = '/opensim/ik_status';
const DEFAULT_OPENSIM_JOINT_STATES_TOPIC = '/opensim/joint_states';
const OPEN_VISUALIZER_SERVICE = '/opensim/visualizer/open';
const TRIGGER_SERVICE_TYPE = 'std_srvs/srv/Trigger';
const SERVICE_TIMEOUT_MS = 10_000;
const VISUALIZER_TIMEOUT_REASON = 'No response from the OpenSim service within 10 s';
const QUAT_SCALE = 1 / 32767;
const CANONICAL_TOPIC_PREFIX = '/esp/raw/';

export interface CanonicalSignalRejection {
  readonly device_id: `esp32:${string}` | null;
  readonly reason: CanonicalSignalRejectionReason;
  readonly rejected_at_ms: number;
  readonly count: number;
  readonly should_announce: boolean;
}

// Phase 24: Mapping workspace topic constants
const MAPPING_CATALOG_TOPIC = '/rehab/model/catalog';
const MAPPING_CURRENT_TOPIC = '/rehab/mapping/current';
const FLEET_REGISTRY_TOPIC = '/esp/fleet/registry';
const CALIBRATION_STATUS_TOPIC = '/rehab/calibration/status';
const INPUT_VALIDITY_TOPIC = '/rehab/opensim/input_validity';

// Phase 24: Mapping service constants
const MAPPING_SET_ASSIGNMENT_SERVICE = '/rehab/mapping/set_assignment';
const MAPPING_APPLY_SERVICE = '/rehab/mapping/apply';
const MAPPING_RESET_SERVICE = '/rehab/mapping/reset';
const IDENTIFY_DEVICE_SERVICE = '/rehab/identify/device';
const GRAVITY = 9.80665;
const CALIBRATION_WINDOW_SECONDS = 0.5;
const STILL_RANGE_RADIANS = 0.08;
const ANGLE_CUTOFF_HZ = 1.5;
const REST_DEADBAND_RADIANS = 0.012;

function numeric(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function normalizeFullMac(value: unknown): `esp32:${string}` | null {
  if (typeof value !== 'string') return null;
  let compact = value;
  if (compact.startsWith('esp32:')) compact = compact.slice(6);
  else if (/^(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$/.test(compact)) compact = compact.replace(/:/g, '');
  if (!/^[0-9a-fA-F]{12}$/.test(compact)) return null;
  return `esp32:${compact.toLowerCase()}`;
}

function optionalFinite(value: unknown): number | null | undefined {
  if (value === null) return null;
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

function optionalString(value: unknown): string | undefined {
  return typeof value === 'string' ? value.slice(0, 240) : undefined;
}

function optionalIdentifier(value: unknown): string | null | undefined {
  if (value === null) return null;
  if (typeof value !== 'string') return undefined;
  const trimmed = value.trim();
  return trimmed ? trimmed.slice(0, 160) : '';
}

function safeServiceMessage(value: unknown, fallback: string): string {
  if (typeof value !== 'string') return fallback;
  const trimmed = value.trim();
  if (
    !trimmed
    || trimmed === 'undefined'
    || trimmed === 'null'
    || trimmed === '[object Object]'
    || trimmed.startsWith('{')
    || trimmed.startsWith('[')
    || trimmed.includes('\n')
    || trimmed.includes('\r')
  ) {
    return fallback;
  }
  return trimmed.replace(/\s+/g, ' ').slice(0, 160);
}

function parseOpenSimStatus(payload: unknown): OpenSimStatusSnapshot | null {
  if (!isRecord(payload)) return null;

  const calibrationRaw = payload.calibration;
  const visualizationRaw = payload.visualization;
  if (
    calibrationRaw !== undefined && !isRecord(calibrationRaw)
    || visualizationRaw !== undefined && !isRecord(visualizationRaw)
  ) {
    return null;
  }

  let calibration: OpenSimStatusSnapshot['calibration'];
  if (isRecord(calibrationRaw)) {
    const state = optionalString(calibrationRaw.state);
    if (
      state === undefined
      || !['UNCALIBRATED', 'CAPTURING', 'CALIBRATED', 'FAILED'].includes(state)
    ) {
      return null;
    }
    const calibrationId = optionalIdentifier(calibrationRaw.calibration_id);
    if (calibrationRaw.calibration_id !== undefined && calibrationId === undefined) return null;
    calibration = {
      state,
      reason: normalizeLiveKneeReason(calibrationRaw.reason, ''),
      known_pose: optionalString(calibrationRaw.known_pose),
      sample_count: optionalFinite(calibrationRaw.sample_count) ?? undefined,
      window_s: optionalFinite(calibrationRaw.window_s) ?? undefined,
      calibration_id: calibrationId,
      has_offsets: typeof calibrationRaw.has_offsets === 'boolean'
        ? calibrationRaw.has_offsets
        : undefined,
    };
  }

  let visualization: OpenSimStatusSnapshot['visualization'];
  if (isRecord(visualizationRaw)) {
    const state = optionalString(visualizationRaw.state)?.toLowerCase();
    if (
      state === undefined
      || !['waiting', 'opening', 'open', 'unavailable', 'failed'].includes(state)
    ) {
      return null;
    }
    visualization = {
      available: typeof visualizationRaw.available === 'boolean'
        ? visualizationRaw.available
        : undefined,
      state,
      reason: normalizeLiveKneeReason(visualizationRaw.reason, ''),
      model_path: optionalString(visualizationRaw.model_path),
    };
  }

  if (!calibration && !visualization && !isRecord(payload.sensors)) return null;
  const sensorsRaw = isRecord(payload.sensors) ? payload.sensors : undefined;
  const parseSensor = (value: unknown) => {
    if (!isRecord(value)) return undefined;
    return {
      state: optionalString(value.state),
      updates: optionalFinite(value.updates) ?? undefined,
      age_s: optionalFinite(value.age_s),
      last_error: normalizeLiveKneeReason(value.last_error, ''),
    };
  };

  return {
    schema: optionalString(payload.schema),
    sensors: sensorsRaw ? {
      master: parseSensor(sensorsRaw.master),
      slave: parseSensor(sensorsRaw.slave),
    } : undefined,
    visualization,
    calibration,
    joint_angle_deg: optionalFinite(payload.joint_angle_deg),
  };
}

function parseOpenSimIkStatus(payload: unknown): OpenSimIkStatusSnapshot | null {
  if (!isRecord(payload) || typeof payload.solution_valid !== 'boolean') return null;
  const calibrationId = optionalIdentifier(payload.calibration_id);
  if (payload.calibration_id !== undefined && calibrationId === undefined) return null;
  for (const key of ['orientation_residual_rms', 'orientation_residual_max', 'input_age_s'] as const) {
    if (payload[key] !== undefined && optionalFinite(payload[key]) === undefined) return null;
  }
  return {
    schema: optionalString(payload.schema),
    solution_valid: payload.solution_valid,
    reason: normalizeLiveKneeReason(payload.reason, payload.solution_valid ? '' : 'No valid OpenSim IK solution'),
    calibration_id: calibrationId,
    orientation_residual_rms: optionalFinite(payload.orientation_residual_rms),
    orientation_residual_max: optionalFinite(payload.orientation_residual_max),
    input_age_s: optionalFinite(payload.input_age_s),
    backend: optionalString(payload.backend),
  };
}

function parseOpenSimJointState(
  payload: unknown,
  receivedAtMs: number,
): OpenSimJointStateSnapshot | null {
  if (!isRecord(payload) || !isRecord(payload.header) || !isRecord(payload.header.stamp)) return null;
  const stamp = {
    sec: payload.header.stamp.sec,
    nanosec: payload.header.stamp.nanosec,
  };
  if (
    !isValidRosStamp(stamp as { sec: number; nanosec: number })
    || !Array.isArray(payload.name)
    || !Array.isArray(payload.position)
    || payload.name.length !== payload.position.length
    || !payload.name.every((name) => typeof name === 'string' && name.length <= 160)
    || !payload.position.every((position) => typeof position === 'number' && Number.isFinite(position))
    || !Number.isFinite(receivedAtMs)
    || receivedAtMs < 0
  ) {
    return null;
  }
  return {
    stamp: { sec: stamp.sec as number, nanosec: stamp.nanosec as number },
    names: [...payload.name] as string[],
    positions: [...payload.position] as number[],
    receivedAtMs,
  };
}

/**
 * Convert a validated raw ESP message to a Frame using the pre-validated SensorConfig.
 * Returns null if the message does not carry the expected topic_schema.
 */
function frameFromRaw(raw: RawEspMessage, config: SensorConfig): Frame | null {
  if (raw.topic_schema !== 'oe_esp32.raw.v1') return null;
  const t = numeric(raw.time_us) / 1_000_000 || performance.now() / 1_000;
  const imu: ImuData = {
    accel: [
      accelCountToMps2(numeric(raw.imu?.ax), config),
      accelCountToMps2(numeric(raw.imu?.ay), config),
      accelCountToMps2(numeric(raw.imu?.az), config),
    ],
    gyro: [
      gyroCountToRad_s(numeric(raw.imu?.gx), config),
      gyroCountToRad_s(numeric(raw.imu?.gy), config),
      gyroCountToRad_s(numeric(raw.imu?.gz), config),
    ],
    quat: [
      numeric(raw.quat?.qw) * QUAT_SCALE,
      numeric(raw.quat?.qx) * QUAT_SCALE,
      numeric(raw.quat?.qy) * QUAT_SCALE,
      numeric(raw.quat?.qz) * QUAT_SCALE,
    ],
    t,
  };
  return {
    t,
    imu,
    force: { fx: 0, fy: 0, fz: 0, mag: 0, t },
    emg: { raw: 0, envelope: 0, channel: 1, t },
    motor: { position: 0, velocity: 0, torque: 0, current: 0, temperature: 0, enabled: false, fault: false, t },
  };
}

function inclination(imu: ImuData): number {
  return Math.atan2(imu.accel[0], Math.hypot(imu.accel[1], imu.accel[2]));
}

/**
 * Keeps the pair angle quiet at rest without masking actual slow limb motion.
 * A fresh acquisition learns its neutral reference only from a quiet 0.5 s span.
 */
class RelativeAngleStabilizer {
  private calibrationSamples: number[] = [];
  private calibrationStartedAt: number | null = null;
  private baseline: number | null = null;
  private filtered: number | null = null;
  private lastTime: number | null = null;

  reset(): void {
    this.calibrationSamples = [];
    this.calibrationStartedAt = null;
    this.baseline = null;
    this.filtered = null;
    this.lastTime = null;
  }

  stabilize(rawAngle: number, now: number): number {
    if (this.baseline === null) {
      this.calibrationStartedAt ??= now;
      this.calibrationSamples.push(rawAngle);

      const low = Math.min(...this.calibrationSamples);
      const high = Math.max(...this.calibrationSamples);
      if (high - low > STILL_RANGE_RADIANS) {
        this.calibrationSamples = [rawAngle];
        this.calibrationStartedAt = now;
      } else if (now - this.calibrationStartedAt >= CALIBRATION_WINDOW_SECONDS) {
        this.baseline = this.calibrationSamples.reduce((sum, value) => sum + value, 0)
          / this.calibrationSamples.length;
        this.filtered = 0;
      }
      this.lastTime = now;
      return 0;
    }

    const target = rawAngle - this.baseline;
    const dt = this.lastTime === null ? 1 / 50 : Math.min(Math.max(now - this.lastTime, 0.005), 0.1);
    const alpha = 1 - Math.exp(-2 * Math.PI * ANGLE_CUTOFF_HZ * dt);
    this.filtered = this.filtered === null ? target : this.filtered + alpha * (target - this.filtered);
    this.lastTime = now;
    return Math.abs(this.filtered) < REST_DEADBAND_RADIANS ? 0 : this.filtered;
  }
}

/**
 * Compute the pair frame from two already-converted Frame objects.
 * If slaveFrame is undefined, return masterFrame directly.
 * Otherwise apply inclination + stabilizer + gyro difference math.
 */
function frameFromPair(
  masterFrame: Frame,
  slaveFrame: Frame | undefined,
  stabilizer: RelativeAngleStabilizer,
): Frame {
  if (!slaveFrame) return masterFrame;

  const relative = stabilizer.stabilize(
    inclination(slaveFrame.imu) - inclination(masterFrame.imu),
    performance.now() / 1_000,
  );
  return {
    ...masterFrame,
    imu: {
      ...masterFrame.imu,
      accel: [Math.sin(relative) * GRAVITY, 0, Math.cos(relative) * GRAVITY],
      gyro: [
        slaveFrame.imu.gyro[0] - masterFrame.imu.gyro[0],
        slaveFrame.imu.gyro[1] - masterFrame.imu.gyro[1],
        slaveFrame.imu.gyro[2] - masterFrame.imu.gyro[2],
      ],
      quat: slaveFrame.imu.quat,
      t: Math.max(masterFrame.t, slaveFrame.t),
    },
  };
}

// ── Phase 24: Guard-parse functions for new mapping topics ───────────────────
// Each follows the parseOpenSimStatus pattern: isRecord + field-type guards.
// Returns null on any validation failure, never throws. (D-10, T-24-05)

export function parseModelCatalog(payload: unknown): ModelCatalogSnapshot | null {
  if (!isRecord(payload)) return null;
  if (typeof payload.model_hash !== 'string') return null;
  if (typeof payload.model_path !== 'string') return null;
  if (!Array.isArray(payload.frame_list)) return null;
  const frame_list: Array<{ path: string; name: string }> = [];
  for (const item of payload.frame_list) {
    if (!isRecord(item)) return null;
    if (typeof item.path !== 'string' || typeof item.name !== 'string') return null;
    frame_list.push({ path: item.path, name: item.name });
  }
  return {
    schema: typeof payload.schema === 'string' ? payload.schema : undefined,
    model_hash: payload.model_hash,
    model_path: payload.model_path,
    frame_list,
  };
}

export function parseMappingCurrent(payload: unknown): MappingCurrentSnapshot | null {
  return parseMappingCurrentSnapshot(payload);
}

export function parseFleetRegistry(payload: unknown): FleetRegistrySnapshot | null {
  if (!isRecord(payload)) return null;
  if (!Array.isArray(payload.devices)) return null;
  const devices: FleetRegistrySnapshot['devices'] = [];
  for (const item of payload.devices) {
    if (!isRecord(item)) return null;
    if (typeof item.device_id !== 'string') return null;
    devices.push({
      device_id: item.device_id,
      role: typeof item.role === 'string' ? item.role : undefined,
      route_state: typeof item.route_state === 'string' ? item.route_state : undefined,
      connection_state: typeof item.connection_state === 'string' ? item.connection_state : undefined,
      rate_hz: typeof item.rate_hz === 'number' && Number.isFinite(item.rate_hz) ? item.rate_hz : undefined,
      drop_count: typeof item.drop_count === 'number' ? item.drop_count : undefined,
    });
  }
  return { devices };
}

export function parseNCalibrationStatus(payload: unknown): NCalibrationStatusSnapshot | null {
  if (!isRecord(payload)) return null;
  const state = payload.state;
  if (state !== 'capturing' && state !== 'calibrated' && state !== 'uncalibrated') return null;
  return {
    state,
    revision: typeof payload.revision === 'number' ? payload.revision : undefined,
    model_hash: typeof payload.model_hash === 'string' ? payload.model_hash : undefined,
  };
}

export function parseInputValidity(payload: unknown): InputValiditySnapshot | null {
  if (!isRecord(payload)) return null;
  if (!isRecord(payload.device_validities)) return null;
  const device_validities: Record<string, boolean> = {};
  for (const [deviceId, valid] of Object.entries(payload.device_validities)) {
    if (typeof valid !== 'boolean') return null;
    device_validities[deviceId] = valid;
  }
  return { device_validities };
}

/** Rosbridge client for the canonical JSON produced by the ROS ESP bridge. */
export class RosbridgeDataSource implements DataSource, OpenSimDataSource {
  private socket: WebSocket | null = null;
  private listeners = new Set<(frame: Frame) => void>();
  private canonicalAcceptedListeners = new Set<(sample: CanonicalSignalSample) => void>();
  private canonicalRejectedListeners = new Set<(rejection: CanonicalSignalRejection) => void>();
  private canonicalTopicTokens = new Map<string, `mac_${string}`>();
  private canonicalRejectionCounts = new Map<string, number>();
  private canonicalLastRejectionReason = new Map<string, CanonicalSignalRejectionReason>();
  private running = false;
  private paused = false;
  private connected = false;
  private receivedFrame = false;
  private masterFrame: Frame | null = null;
  private slaveFrame: Frame | null = null;
  private _warnedScale = false;
  private readonly angleStabilizer = new RelativeAngleStabilizer();
  private connectionGeneration = 0;
  private nextServiceCallId = 0;
  private pendingServiceCalls = new Map<string, {
    resolve: (result: RecordingCommandResult) => void;
    timeout: number;
    toResult: (values: RosbridgeEnvelope['values']) => RecordingCommandResult;
    generation: number;
    socket: WebSocket;
  }>();

  constructor(
    private readonly url = import.meta.env.VITE_ROSBRIDGE_URL || DEFAULT_URL,
    private readonly masterTopic = import.meta.env.VITE_ESP_RAW_TOPIC || DEFAULT_MASTER_TOPIC,
    private readonly slaveTopic = import.meta.env.VITE_ESP_SLAVE_TOPIC || DEFAULT_SLAVE_TOPIC,
    private readonly onUnavailable?: () => void,
    private readonly onConnectionChange?: (connected: boolean) => void,
    private readonly onFrameReceived?: () => void,
    private readonly onPairHealth?: (health: PairHealthSnapshot) => void,
    private readonly onWarnScaleMissing?: (deviceList: string) => void,
    private readonly onOpenSimStatus?: (status: OpenSimStatusSnapshot) => void,
    private readonly onOpenSimIkStatus?: (status: OpenSimIkStatusSnapshot) => void,
    private readonly onOpenSimJointState?: (jointState: OpenSimJointStateSnapshot) => void,
    // Phase 24: Mapping workspace callbacks (positions 12-16, all optional, appended after position 11)
    private readonly onModelCatalog?: (catalog: ModelCatalogSnapshot) => void,
    private readonly onMappingCurrent?: (state: MappingCurrentSnapshot) => void,
    private readonly onFleetRegistry?: (registry: FleetRegistrySnapshot) => void,
    private readonly onCalibrationStatus?: (status: NCalibrationStatusSnapshot) => void,
    private readonly onInputValidity?: (validity: InputValiditySnapshot) => void,
  ) {}

  start(_rateHz: number): void {
    this.running = true;
    this.paused = false;
    // Reset all connection state before creating a new WebSocket (T-09-03, T-09-04)
    this._warnedScale = false;
    this.masterFrame = null;
    this.slaveFrame = null;
    this.receivedFrame = false;
    this.angleStabilizer.reset();
    if (this.socket) return;
    this.canonicalTopicTokens.clear();
    this.canonicalRejectionCounts.clear();
    this.canonicalLastRejectionReason.clear();
    const generation = ++this.connectionGeneration;
    const socket = new WebSocket(this.url);
    this.socket = socket;
    socket.onopen = () => {
      if (!this.isCurrentSession(generation, socket)) return;
      this.connected = true;
      this.onConnectionChange?.(true);
      const subscriptions = [
        [this.masterTopic, 'std_msgs/msg/String'],
        [this.slaveTopic, 'std_msgs/msg/String'],
        [DEFAULT_PAIR_HEALTH_TOPIC, 'std_msgs/msg/String'],
        [DEFAULT_OPENSIM_STATUS_TOPIC, 'std_msgs/msg/String'],
        [DEFAULT_OPENSIM_IK_STATUS_TOPIC, 'std_msgs/msg/String'],
        [DEFAULT_OPENSIM_JOINT_STATES_TOPIC, 'sensor_msgs/msg/JointState'],
        // Phase 24: Mapping workspace subscriptions (D-09)
        [MAPPING_CATALOG_TOPIC, 'std_msgs/msg/String'],
        [MAPPING_CURRENT_TOPIC, 'std_msgs/msg/String'],
        [FLEET_REGISTRY_TOPIC, 'std_msgs/msg/String'],
        [CALIBRATION_STATUS_TOPIC, 'std_msgs/msg/String'],
        [INPUT_VALIDITY_TOPIC, 'std_msgs/msg/String'],
      ] as const;
      for (const [topic, type] of new Map(subscriptions.map((entry) => [entry[0], entry])).values()) {
        socket.send(JSON.stringify({ op: 'subscribe', topic, type }));
      }
    };
    socket.onmessage = (event) => this.handleMessage(event.data, generation, socket);
    socket.onerror = () => {
      if (!this.isCurrentSession(generation, socket)) return;
      if (!this.connected) this.onUnavailable?.();
    };
    socket.onclose = () => {
      if (!this.isCurrentSession(generation, socket)) return;
      const unavailable = !this.connected;
      this.connected = false;
      this.onConnectionChange?.(false);
      this.socket = null;
      this.rejectPendingServiceCalls(
        'ROS connection closed before the command completed',
        generation,
        socket,
      );
      if (this.running && unavailable) this.onUnavailable?.();
    };
  }

  stop(): void {
    this.running = false;
    this.paused = false;
    this.angleStabilizer.reset();
    const socket = this.socket;
    const generation = this.connectionGeneration;
    this.socket = null;
    this.connected = false;
    if (socket) {
      this.rejectPendingServiceCalls(
        'ROS connection closed before the command completed',
        generation,
        socket,
      );
      socket.close();
    }
  }

  pause(): void { this.paused = true; }
  resume(): void { this.paused = false; }
  setSampleRate(_rateHz: number): void {}

  subscribe(callback: (frame: Frame) => void): () => void {
    this.listeners.add(callback);
    return () => this.listeners.delete(callback);
  }

  subscribeCanonicalAccepted(callback: (sample: CanonicalSignalSample) => void): () => void {
    this.canonicalAcceptedListeners.add(callback);
    return () => this.canonicalAcceptedListeners.delete(callback);
  }

  subscribeCanonicalRejected(callback: (rejection: CanonicalSignalRejection) => void): () => void {
    this.canonicalRejectedListeners.add(callback);
    return () => this.canonicalRejectedListeners.delete(callback);
  }

  setRecording(on: boolean): Promise<RecordingCommandResult> {
    return this.callService('/esp/recording/set', { data: on });
  }

  /** Begin OpenSim reference-pose capture (standing, knees extended). */
  captureCalibration(): Promise<RecordingCommandResult> {
    return this.callService(
      '/opensim/calibration/capture',
      {},
      'std_srvs/srv/Trigger',
    );
  }

  /** Clear OpenSim mounting-offset calibration → UNCALIBRATED. */
  clearCalibration(): Promise<RecordingCommandResult> {
    return this.callService(
      '/opensim/calibration/clear',
      {},
      'std_srvs/srv/Trigger',
    );
  }

  /** Ask the backend-owned OpenSim adapter to show its native visualizer. */
  openVisualizer(): Promise<RecordingCommandResult> {
    return this.callService(
      OPEN_VISUALIZER_SERVICE,
      {},
      TRIGGER_SERVICE_TYPE,
      (values) => ({
        success: values?.success === true,
        message: normalizeLiveKneeReason(
          values?.message,
          values?.success === true
            ? 'OpenSim visualizer request accepted'
            : 'OpenSim visualizer could not open',
        ),
      }),
      VISUALIZER_TIMEOUT_REASON,
    );
  }

  requestSampleRate(rateHz: number): Promise<RecordingCommandResult> {
    return this.requestImuControl('sample_rate_hz', rateHz);
  }

  requestImuControl(name: ImuControlParameter, value: number | boolean): Promise<RecordingCommandResult> {
    const parameterValue = typeof value === 'boolean'
      ? { type: 1, bool_value: value }
      : { type: 2, integer_value: value };

    const args = {
      parameters: [{
        name,
        value: parameterValue,
      }],
    };

    const serviceType = 'rcl_interfaces/srv/SetParameters';

    const toMasterResult = (values: RosbridgeEnvelope['values']): RecordingCommandResult => {
      const result = values?.results?.[0];
      return {
        success: result?.successful === true,
        message: result?.reason || (result?.successful ? `Confirmed ${name}` : `Master rejected ${name}`),
      };
    };

    // For accel_range_g and gyro_range_dps, call BOTH master and slave services
    // and coordinate the ACKs (T-09-01: DATA-01 requirement)
    if (name === 'accel_range_g' || name === 'gyro_range_dps') {
      return this.callBothRangeServices(name, args, serviceType, value);
    }

    // For other parameters (sample_rate_hz, filter_enabled, effective_sample_rate_hz),
    // only master needs the explicit call (these propagate via ESP-NOW)
    return this.callService(
      '/esp_bridge_master/set_parameters',
      args,
      serviceType,
      toMasterResult,
    );
  }

  /**
   * Call both master and slave services for range-affecting parameters.
   * Reports success only when both succeed. If master succeeds and slave fails,
   * attempts a compensating restore of the master to the prior value.
   */
  private async callBothRangeServices(
    name: ImuControlParameter,
    args: Record<string, unknown>,
    serviceType: string,
    newValue: number | boolean,
  ): Promise<RecordingCommandResult> {
    if (!this.socket || !this.connected) {
      return { success: false, message: 'ROS bridge is not connected' };
    }

    const toMasterResult = (values: RosbridgeEnvelope['values']): RecordingCommandResult => {
      const result = values?.results?.[0];
      return {
        success: result?.successful === true,
        message: result?.reason || (result?.successful ? `Confirmed ${name}` : `Master rejected ${name}`),
      };
    };

    const toSlaveResult = (values: RosbridgeEnvelope['values']): RecordingCommandResult => {
      const result = values?.results?.[0];
      return {
        success: result?.successful === true,
        message: result?.reason || (result?.successful ? `Confirmed ${name}` : `Slave rejected ${name}`),
      };
    };

    // Call both services in parallel
    const [masterResult, slaveResult] = await Promise.all([
      this.callService('/esp_bridge_master/set_parameters', args, serviceType, toMasterResult),
      this.callService('/esp_bridge_slave/set_parameters', args, serviceType, toSlaveResult),
    ]);

    if (masterResult.success && slaveResult.success) {
      return { success: true, message: `Confirmed ${name} on master and slave` };
    }

    if (masterResult.success && !slaveResult.success) {
      // Attempt to restore master to prior value via a compensating request.
      // We don't have the prior value readily available, so log the failure.
      // The compensating call uses the opposite value when it's a boolean; for
      // numeric range parameters we cannot know the prior value without extra state,
      // so we log the partial failure and return false. The caller should handle this.
      console.warn(`[RosbridgeDataSource] Partial ${name} update: master succeeded, slave failed (${slaveResult.message}). Master may now be out of sync.`);
      return {
        success: false,
        message: `Partial update: master confirmed ${name} but slave rejected it (${slaveResult.message}). Master state may be inconsistent; reconnect recommended.`,
      };
    }

    if (!masterResult.success && slaveResult.success) {
      return {
        success: false,
        message: `Master rejected ${name} (${masterResult.message}); slave confirmed. Reconnect recommended.`,
      };
    }

    return {
      success: false,
      message: `Both master and slave rejected ${name}: master=${masterResult.message}; slave=${slaveResult.message}`,
    };
  }

  // ── Phase 24: Mapping service call methods (D-11, D-17) ─────────────────

  /** Call /rehab/mapping/set_assignment — assign a device to a segment/frame. */
  callSetAssignment(
    deviceId: string,
    segment: string,
    frame: string,
    state: string,
  ): Promise<RecordingCommandResult> {
    return this.callService(
      MAPPING_SET_ASSIGNMENT_SERVICE,
      { device_id: deviceId, segment, frame, state },
      'rehab_robotics_interfaces/srv/SetAssignment',
      (values) => {
        const v = values as Record<string, unknown> | undefined;
        const outcome = String(v?.outcome ?? '');
        const detail = String(v?.detail ?? '');
        return { success: outcome === 'ok', message: outcome || detail, outcome, detail } as RecordingCommandResult;
      },
      'Timed out waiting for SetAssignment response',
    );
  }

  /** Call /rehab/mapping/apply — atomically apply all current assignments. */
  callApplyMapping(expectedRevision: number): Promise<RecordingCommandResult> {
    return this.callService(
      MAPPING_APPLY_SERVICE,
      { expected_revision: expectedRevision },
      'rehab_robotics_interfaces/srv/ApplyMapping',
      (values) => {
        const v = values as Record<string, unknown> | undefined;
        const outcome = String(v?.outcome ?? '');
        const detail = String(v?.detail ?? '');
        const appliedRevision = typeof v?.applied_revision === 'number' ? v.applied_revision : 0;
        return {
          success: outcome === 'applied',
          message: outcome || detail,
          outcome,
          detail,
          appliedRevision,
        } as RecordingCommandResult;
      },
      'Timed out waiting for ApplyMapping response',
    );
  }

  /** Call /rehab/mapping/reset — reset all assignments for the given model hash. */
  callResetMapping(modelHash: string): Promise<RecordingCommandResult> {
    return this.callService(
      MAPPING_RESET_SERVICE,
      { model_hash: modelHash },
      'rehab_robotics_interfaces/srv/ResetMapping',
      (values) => {
        const v = values as Record<string, unknown> | undefined;
        const outcome = String(v?.outcome ?? '');
        return { success: outcome === 'ok', message: outcome, outcome } as RecordingCommandResult;
      },
      'Timed out waiting for ResetMapping response',
    );
  }

  /** Call /rehab/identify/device — trigger LED flash on a device for physical identification. */
  callIdentifyDevice(deviceId: string, timeoutMs = 5000): Promise<RecordingCommandResult> {
    return this.callService(
      IDENTIFY_DEVICE_SERVICE,
      { device_id: deviceId, timeout_ms: timeoutMs },
      'rehab_robotics_interfaces/srv/IdentifyDevice',
      (values) => {
        const v = values as Record<string, unknown> | undefined;
        const outcome = String(v?.outcome ?? '');
        return { success: outcome !== '', message: outcome, outcome } as RecordingCommandResult;
      },
      'Timed out waiting for IdentifyDevice response',
    );
  }

  private callService(
    service: string,
    args: Record<string, unknown>,
    type = 'std_srvs/srv/SetBool',
    toResult = (values: RosbridgeEnvelope['values']): RecordingCommandResult => ({
      success: values?.success === true,
      message: safeServiceMessage(values?.message, 'Master returned an empty response'),
    }),
    timeoutMessage = 'Timed out waiting for the master recording response',
  ): Promise<RecordingCommandResult> {
    const socket = this.socket;
    const generation = this.connectionGeneration;
    if (!socket || !this.connected || !this.isCurrentSession(generation, socket)) {
      return Promise.resolve({ success: false, message: 'ROS bridge is not connected' });
    }
    const id = `service-${generation}-${++this.nextServiceCallId}`;
    return new Promise((resolve) => {
      const timeout = window.setTimeout(() => {
        const pending = this.pendingServiceCalls.get(id);
        if (
          !pending
          || pending.generation !== generation
          || pending.socket !== socket
          || !this.isCurrentSession(generation, socket)
        ) return;
        this.pendingServiceCalls.delete(id);
        resolve({ success: false, message: timeoutMessage });
      }, SERVICE_TIMEOUT_MS);
      this.pendingServiceCalls.set(id, {
        resolve,
        timeout,
        toResult,
        generation,
        socket,
      });
      socket.send(JSON.stringify({
        op: 'call_service',
        id,
        service,
        type,
        args,
      }));
    });
  }

  private handleMessage(
    payload: unknown,
    generation = this.connectionGeneration,
    socket = this.socket,
  ): void {
    if (generation !== this.connectionGeneration || socket !== this.socket) return;
    if (this.paused || typeof payload !== 'string') return;
    try {
      const envelope = JSON.parse(payload) as RosbridgeEnvelope;
      if (envelope.op === 'service_response' && envelope.id) {
        const pending = this.pendingServiceCalls.get(envelope.id);
        if (
          !pending
          || pending.generation !== generation
          || pending.socket !== socket
          || !socket
        ) return;
        this.pendingServiceCalls.delete(envelope.id);
        window.clearTimeout(pending.timeout);
        let result: RecordingCommandResult;
        try {
          result = pending.toResult(envelope.values);
        } catch {
          result = { success: false, message: 'ROS service returned an invalid response' };
        }
        pending.resolve(result);
        return;
      }
      if (envelope.op !== 'publish' || !isRecord(envelope.msg)) return;

      if (envelope.topic === DEFAULT_PAIR_HEALTH_TOPIC) {
        if (typeof envelope.msg.data !== 'string') return;
        this.onPairHealth?.(JSON.parse(envelope.msg.data) as PairHealthSnapshot);
        return;
      }
      if (envelope.topic === DEFAULT_OPENSIM_STATUS_TOPIC) {
        if (typeof envelope.msg.data !== 'string') return;
        const status = parseOpenSimStatus(JSON.parse(envelope.msg.data));
        if (status) this.onOpenSimStatus?.(status);
        return;
      }
      if (envelope.topic === DEFAULT_OPENSIM_IK_STATUS_TOPIC) {
        if (typeof envelope.msg.data !== 'string') return;
        const status = parseOpenSimIkStatus(JSON.parse(envelope.msg.data));
        if (status) this.onOpenSimIkStatus?.(status);
        return;
      }
      if (envelope.topic === DEFAULT_OPENSIM_JOINT_STATES_TOPIC) {
        const jointState = parseOpenSimJointState(envelope.msg, performance.now());
        if (jointState) this.onOpenSimJointState?.(jointState);
        return;
      }

      // Phase 24: Mapping workspace topic dispatch (D-10)
      // Each block: parse msg.data as JSON, guard with parse function, call callback only when non-null.
      // Invalid payloads are silently dropped — never throw. (T-24-05)
      if (envelope.topic === MAPPING_CATALOG_TOPIC) {
        if (typeof envelope.msg.data !== 'string') return;
        try {
          const catalog = parseModelCatalog(JSON.parse(envelope.msg.data));
          if (catalog) this.onModelCatalog?.(catalog);
        } catch { /* malformed JSON silently dropped */ }
        return;
      }
      if (envelope.topic === MAPPING_CURRENT_TOPIC) {
        if (typeof envelope.msg.data !== 'string') return;
        try {
          const mapping = parseMappingCurrent(JSON.parse(envelope.msg.data));
          if (mapping) this.onMappingCurrent?.(mapping);
        } catch { /* malformed JSON silently dropped */ }
        return;
      }
      if (envelope.topic === FLEET_REGISTRY_TOPIC) {
        if (typeof envelope.msg.data !== 'string') return;
        try {
          const registry = parseFleetRegistry(JSON.parse(envelope.msg.data));
          if (registry) {
            this.reconcileCanonicalTopics(registry, generation, socket);
            this.onFleetRegistry?.(registry);
          }
        } catch { /* malformed JSON silently dropped */ }
        return;
      }
      if (envelope.topic === CALIBRATION_STATUS_TOPIC) {
        if (typeof envelope.msg.data !== 'string') return;
        try {
          const status = parseNCalibrationStatus(JSON.parse(envelope.msg.data));
          if (status) this.onCalibrationStatus?.(status);
        } catch { /* malformed JSON silently dropped */ }
        return;
      }
      if (envelope.topic === INPUT_VALIDITY_TOPIC) {
        if (typeof envelope.msg.data !== 'string') return;
        try {
          const validity = parseInputValidity(JSON.parse(envelope.msg.data));
          if (validity) this.onInputValidity?.(validity);
        } catch { /* malformed JSON silently dropped */ }
        return;
      }

      const expectedTopicToken = typeof envelope.topic === 'string'
        ? this.canonicalTopicTokens.get(envelope.topic)
        : undefined;
      if (expectedTopicToken) {
        const deviceId = `esp32:${expectedTopicToken.slice(4)}` as `esp32:${string}`;
        if (typeof envelope.msg.data !== 'string') {
          this.emitCanonicalRejection(deviceId, 'schema_invalid');
          return;
        }
        let raw: unknown;
        try {
          const transportPayload = JSON.parse(envelope.msg.data) as unknown;
          raw = isRecord(transportPayload) ? transportPayload.sample_contract : undefined;
        } catch {
          this.emitCanonicalRejection(deviceId, 'schema_invalid');
          return;
        }
        const result = parseCanonicalSignalSample(raw, expectedTopicToken);
        if (!result.ok) {
          this.emitCanonicalRejection(
            deviceId,
            result.reason === 'canonical_parser_unimplemented' ? 'schema_invalid' : result.reason,
          );
          return;
        }
        this.canonicalAcceptedListeners.forEach((listener) => listener(result.value));
        return;
      }

      if (typeof envelope.msg.data !== 'string') return;

      const isMaster = envelope.topic === this.masterTopic;
      const isSlave  = envelope.topic === this.slaveTopic;
      if (!isMaster && !isSlave) return;

      const raw = JSON.parse(envelope.msg.data) as RawEspMessage;
      const role = isMaster ? 'MASTER' : 'SLAVE';

      // Validate sensor_config before any caching (T-09-01, DATA-02)
      const configResult = validateSensorConfig(raw.sensor_config);
      if (!configResult.ok) {
        // Warn exactly once per connection (T-09-03)
        if (!this._warnedScale) {
          this._warnedScale = true;
          this.onWarnScaleMissing?.(role);
        }
        // Do NOT update masterFrame/slaveFrame; do NOT emit
        return;
      }

      // Convert independently from validated config
      const frame = frameFromRaw(raw, configResult.value);
      if (!frame) return;

      if (isMaster) this.masterFrame = frame;
      if (isSlave)  this.slaveFrame  = frame;

      // Emit whenever we have a valid master frame.
      // If masterFrame is null and we only have slave, do not emit (slave without master is not useful).
      if (this.masterFrame === null) return;

      const emission = frameFromPair(
        this.masterFrame,
        this.slaveFrame ?? undefined,
        this.angleStabilizer,
      );

      if (!this.receivedFrame) {
        this.receivedFrame = true;
        this.onFrameReceived?.();
      }
      this.listeners.forEach((listener) => listener(emission));
    } catch {
      // A malformed or unrelated rosbridge message must not interrupt acquisition.
    }
  }

  private isCurrentSession(generation: number, socket: WebSocket): boolean {
    return generation === this.connectionGeneration && socket === this.socket;
  }

  private reconcileCanonicalTopics(
    registry: FleetRegistrySnapshot,
    generation: number,
    socket: WebSocket | null,
  ): void {
    if (!socket || !this.connected || !this.isCurrentSession(generation, socket)) return;
    const desired = new Map<string, `mac_${string}`>();
    for (const row of registry.devices) {
      const deviceId = normalizeFullMac(row.device_id);
      if (!deviceId) continue;
      const token = `mac_${deviceId.slice(6)}` as `mac_${string}`;
      desired.set(`${CANONICAL_TOPIC_PREFIX}${token}`, token);
    }
    for (const topic of this.canonicalTopicTokens.keys()) {
      if (!desired.has(topic)) socket.send(JSON.stringify({ op: 'unsubscribe', topic }));
    }
    for (const topic of desired.keys()) {
      if (!this.canonicalTopicTokens.has(topic)) {
        socket.send(JSON.stringify({ op: 'subscribe', topic, type: 'std_msgs/msg/String' }));
      }
    }
    this.canonicalTopicTokens = desired;
  }

  private emitCanonicalRejection(
    deviceId: `esp32:${string}` | null,
    reason: CanonicalSignalRejectionReason,
  ): void {
    const sourceKey = deviceId ?? 'unknown';
    const count = Math.min(
      Number.MAX_SAFE_INTEGER,
      (this.canonicalRejectionCounts.get(sourceKey) ?? 0) + 1,
    );
    const shouldAnnounce = this.canonicalLastRejectionReason.get(sourceKey) !== reason;
    this.canonicalRejectionCounts.set(sourceKey, count);
    this.canonicalLastRejectionReason.set(sourceKey, reason);
    const event = Object.freeze({
      device_id: deviceId,
      reason,
      rejected_at_ms: Math.min(Number.MAX_SAFE_INTEGER, Math.max(0, Math.trunc(Date.now()))),
      count,
      should_announce: shouldAnnounce,
    });
    this.canonicalRejectedListeners.forEach((listener) => listener(event));
  }

  private rejectPendingServiceCalls(
    message: string,
    generation: number,
    socket: WebSocket,
  ): void {
    for (const [id, pending] of this.pendingServiceCalls.entries()) {
      if (pending.generation !== generation || pending.socket !== socket) continue;
      window.clearTimeout(pending.timeout);
      pending.resolve({ success: false, message });
      this.pendingServiceCalls.delete(id);
    }
  }
}
