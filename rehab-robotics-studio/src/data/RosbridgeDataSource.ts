import type { DataSource } from './DataSource';
import type { Frame, ImuData } from '../types/signals';

type RawEspMessage = {
  topic_schema?: string;
  time_us?: number;
  imu?: Partial<Record<'ax' | 'ay' | 'az' | 'gx' | 'gy' | 'gz', number>>;
  quat?: Partial<Record<'qw' | 'qx' | 'qy' | 'qz', number>>;
};

type RosbridgeEnvelope = {
  op?: string;
  topic?: string;
  msg?: { data?: string };
};

const DEFAULT_URL = 'ws://127.0.0.1:9090';
const DEFAULT_MASTER_TOPIC = '/esp/raw/master';
const DEFAULT_SLAVE_TOPIC = '/esp/raw/slave';
const ACC_SCALE = 9.80665 / 16384;
const GYRO_SCALE = (Math.PI / 180) / 131.072;
const QUAT_SCALE = 1 / 32767;
const GRAVITY = 9.80665;
const CALIBRATION_WINDOW_SECONDS = 0.5;
const STILL_RANGE_RADIANS = 0.08;
const ANGLE_CUTOFF_HZ = 1.5;
const REST_DEADBAND_RADIANS = 0.012;

function numeric(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0;
}

function frameFromRaw(raw: RawEspMessage): Frame | null {
  if (raw.topic_schema !== 'oe_esp32.raw.v1') return null;
  const t = numeric(raw.time_us) / 1_000_000 || performance.now() / 1_000;
  const imu: ImuData = {
    accel: [numeric(raw.imu?.ax) * ACC_SCALE, numeric(raw.imu?.ay) * ACC_SCALE, numeric(raw.imu?.az) * ACC_SCALE],
    gyro: [numeric(raw.imu?.gx) * GYRO_SCALE, numeric(raw.imu?.gy) * GYRO_SCALE, numeric(raw.imu?.gz) * GYRO_SCALE],
    quat: [numeric(raw.quat?.qw) * QUAT_SCALE, numeric(raw.quat?.qx) * QUAT_SCALE, numeric(raw.quat?.qy) * QUAT_SCALE, numeric(raw.quat?.qz) * QUAT_SCALE],
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

function frameFromPair(
  masterRaw: RawEspMessage,
  slaveRaw: RawEspMessage | undefined,
  stabilizer: RelativeAngleStabilizer,
): Frame | null {
  const master = frameFromRaw(masterRaw);
  if (!master || !slaveRaw) return master;
  const slave = frameFromRaw(slaveRaw);
  if (!slave) return master;

  const relative = stabilizer.stabilize(
    inclination(slave.imu) - inclination(master.imu),
    performance.now() / 1_000,
  );
  return {
    ...master,
    imu: {
      ...master.imu,
      accel: [Math.sin(relative) * GRAVITY, 0, Math.cos(relative) * GRAVITY],
      gyro: [
        slave.imu.gyro[0] - master.imu.gyro[0],
        slave.imu.gyro[1] - master.imu.gyro[1],
        slave.imu.gyro[2] - master.imu.gyro[2],
      ],
      quat: slave.imu.quat,
      t: Math.max(master.t, slave.t),
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
  private masterRaw: RawEspMessage | null = null;
  private slaveRaw: RawEspMessage | null = null;
  private readonly angleStabilizer = new RelativeAngleStabilizer();

  constructor(
    private readonly url = import.meta.env.VITE_ROSBRIDGE_URL || DEFAULT_URL,
    private readonly masterTopic = import.meta.env.VITE_ESP_RAW_TOPIC || DEFAULT_MASTER_TOPIC,
    private readonly slaveTopic = import.meta.env.VITE_ESP_SLAVE_TOPIC || DEFAULT_SLAVE_TOPIC,
    private readonly onUnavailable?: () => void,
    private readonly onConnectionChange?: (connected: boolean) => void,
    private readonly onFrameReceived?: () => void,
  ) {}

  start(_rateHz: number): void {
    this.running = true;
    this.paused = false;
    this.angleStabilizer.reset();
    if (this.socket) return;
    this.socket = new WebSocket(this.url);
    this.socket.onopen = () => {
      this.connected = true;
      this.onConnectionChange?.(true);
      for (const topic of new Set([this.masterTopic, this.slaveTopic])) {
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

  private handleMessage(payload: unknown): void {
    if (this.paused || typeof payload !== 'string') return;
    try {
      const envelope = JSON.parse(payload) as RosbridgeEnvelope;
      if (envelope.op !== 'publish' || !envelope.msg?.data) return;
      if (envelope.topic !== this.masterTopic && envelope.topic !== this.slaveTopic) return;
      const raw = JSON.parse(envelope.msg.data) as RawEspMessage;
      if (envelope.topic === this.masterTopic) this.masterRaw = raw;
      if (envelope.topic === this.slaveTopic) this.slaveRaw = raw;
      const frame = frameFromPair(this.masterRaw ?? raw, this.slaveRaw ?? undefined, this.angleStabilizer);
      if (frame) {
        if (!this.receivedFrame) {
          this.receivedFrame = true;
          this.onFrameReceived?.();
        }
        this.listeners.forEach((listener) => listener(frame));
      }
    } catch {
      // A malformed or unrelated rosbridge message must not interrupt acquisition.
    }
  }
}
