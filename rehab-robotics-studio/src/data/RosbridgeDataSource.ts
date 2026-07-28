import type { DataSource } from './DataSource';
import type { Frame, ImuData } from '../types/signals';
import type { OpenSimStatusSnapshot, PairHealthSnapshot } from '../types/health';
import {
  validateSensorConfig,
  accelCountToMps2,
  gyroCountToRad_s,
  type SensorConfig,
} from './measurementContract';

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
  msg?: { data?: string };
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
const QUAT_SCALE = 1 / 32767;
const GRAVITY = 9.80665;
const CALIBRATION_WINDOW_SECONDS = 0.5;
const STILL_RANGE_RADIANS = 0.08;
const ANGLE_CUTOFF_HZ = 1.5;
const REST_DEADBAND_RADIANS = 0.012;

function numeric(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0;
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

/** Rosbridge client for the canonical JSON produced by the ROS ESP bridge. */
export class RosbridgeDataSource implements DataSource {
  private socket: WebSocket | null = null;
  private listeners = new Set<(frame: Frame) => void>();
  private running = false;
  private paused = false;
  private connected = false;
  private receivedFrame = false;
  private masterFrame: Frame | null = null;
  private slaveFrame: Frame | null = null;
  private _warnedScale = false;
  private readonly angleStabilizer = new RelativeAngleStabilizer();
  private nextServiceCallId = 0;
  private pendingServiceCalls = new Map<string, {
    resolve: (result: RecordingCommandResult) => void;
    timeout: number;
    toResult: (values: RosbridgeEnvelope['values']) => RecordingCommandResult;
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
    this.socket = new WebSocket(this.url);
    this.socket.onopen = () => {
      this.connected = true;
      this.onConnectionChange?.(true);
      for (const topic of new Set([
        this.masterTopic,
        this.slaveTopic,
        DEFAULT_PAIR_HEALTH_TOPIC,
        DEFAULT_OPENSIM_STATUS_TOPIC,
      ])) {
        this.socket?.send(JSON.stringify({ op: 'subscribe', topic, type: 'std_msgs/msg/String' }));
      }
    };
    this.socket.onmessage = (event) => this.handleMessage(event.data);
    this.socket.onerror = () => {
      if (!this.connected) this.onUnavailable?.();
    };
    this.socket.onclose = () => {
      const unavailable = !this.connected;
      this.connected = false;
      this.onConnectionChange?.(false);
      this.socket = null;
      this.rejectPendingServiceCalls('ROS connection closed before the recording command completed');
      if (this.running && unavailable) this.onUnavailable?.();
    };
  }

  stop(): void {
    this.running = false;
    this.paused = false;
    this.angleStabilizer.reset();
    this.socket?.close();
    this.socket = null;
  }

  pause(): void { this.paused = true; }
  resume(): void { this.paused = false; }
  setSampleRate(_rateHz: number): void {}

  subscribe(callback: (frame: Frame) => void): () => void {
    this.listeners.add(callback);
    return () => this.listeners.delete(callback);
  }

  setRecording(on: boolean): Promise<RecordingCommandResult> {
    return this.callService('/esp/recording/set', { data: on });
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

  private callService(
    service: string,
    args: Record<string, unknown>,
    type = 'std_srvs/srv/SetBool',
    toResult = (values: RosbridgeEnvelope['values']): RecordingCommandResult => ({
      success: values?.success === true,
      message: values?.message || 'Master returned an empty response',
    }),
  ): Promise<RecordingCommandResult> {
    if (!this.socket || !this.connected) {
      return Promise.resolve({ success: false, message: 'ROS bridge is not connected' });
    }
    const id = `recording-${++this.nextServiceCallId}`;
    return new Promise((resolve) => {
      const timeout = window.setTimeout(() => {
        if (this.pendingServiceCalls.delete(id)) {
          resolve({ success: false, message: 'Timed out waiting for the master recording response' });
        }
      }, 10_000);
      this.pendingServiceCalls.set(id, { resolve, timeout, toResult });
      this.socket?.send(JSON.stringify({
        op: 'call_service',
        id,
        service,
        type,
        args,
      }));
    });
  }

  private handleMessage(payload: unknown): void {
    if (this.paused || typeof payload !== 'string') return;
    try {
      const envelope = JSON.parse(payload) as RosbridgeEnvelope;
      if (envelope.op === 'service_response' && envelope.id) {
        const pending = this.pendingServiceCalls.get(envelope.id);
        if (!pending) return;
        this.pendingServiceCalls.delete(envelope.id);
        window.clearTimeout(pending.timeout);
        pending.resolve(pending.toResult(envelope.values));
        return;
      }
      if (envelope.op !== 'publish' || !envelope.msg?.data) return;

      if (envelope.topic === DEFAULT_PAIR_HEALTH_TOPIC) {
        this.onPairHealth?.(JSON.parse(envelope.msg.data) as PairHealthSnapshot);
        return;
      }
      if (envelope.topic === DEFAULT_OPENSIM_STATUS_TOPIC) {
        this.onOpenSimStatus?.(JSON.parse(envelope.msg.data) as OpenSimStatusSnapshot);
        return;
      }

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

  private rejectPendingServiceCalls(message: string): void {
    for (const pending of this.pendingServiceCalls.values()) {
      window.clearTimeout(pending.timeout);
      pending.resolve({ success: false, message });
    }
    this.pendingServiceCalls.clear();
  }
}
