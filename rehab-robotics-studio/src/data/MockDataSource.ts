import type { DataSource } from './DataSource';
import type { Frame, ForceData, EmgData, ImuData, MotorState } from '../types/signals';

class MockDataSource implements DataSource {
  private timer: ReturnType<typeof setInterval> | null = null;
  private rate = 1000;
  private paused = false;
  private time = 0;
  private lastWall = 0;
  private listeners = new Set<(frame: Frame) => void>();

  start(rateHz: number): void { this.rate = rateHz; this.paused = false; this.lastWall = performance.now(); this.restart(); }
  stop(): void { if (this.timer !== null) { clearInterval(this.timer); this.timer = null; } }
  pause(): void { this.paused = true; }
  resume(): void { this.paused = false; this.lastWall = performance.now(); }
  setSampleRate(rateHz: number): void { this.rate = rateHz; if (this.timer !== null && !this.paused) this.restart(); }
  subscribe(callback: (frame: Frame) => void): () => void { this.listeners.add(callback); return () => { this.listeners.delete(callback); }; }

  private restart(): void {
    this.stop();
    this.timer = setInterval(() => this.tick(), Math.min(40, Math.max(8, Math.round(1000 / this.rate))));
  }
  private tick(): void {
    if (this.paused) return;
    const now = performance.now();
    this.time += Math.min(0.1, (now - this.lastWall) / 1000);
    this.lastWall = now;
    const frame = this.generate(this.time);
    this.listeners.forEach((listener) => listener(frame));
  }
  private generate(time: number): Frame {
    const fz = 10 * Math.sin(2 * Math.PI * time) + (Math.random() * 2 - 1) * 1.5;
    const force: ForceData = { fx: 0.8 * Math.sin(2 * Math.PI * 0.7 * time), fy: 0.6 * Math.cos(2 * Math.PI * 0.5 * time), fz, mag: Math.abs(fz), t: time };
    const raw = Math.sin(2 * Math.PI * 1.3 * time) * (0.4 + 0.3 * Math.random());
    const emg: EmgData = { raw, envelope: Math.abs(raw), channel: 1, t: time };
    const angle = 2 * Math.PI * 0.35 * time;
    const imu: ImuData = { quat: [Math.cos(angle / 2), 0, 0, Math.sin(angle / 2)], accel: [0.1 * Math.sin(angle), 0.1 * Math.cos(angle), 9.81], gyro: [0, 0, 0.35 * Math.cos(angle)], t: time };
    const motor: MotorState = { position: 12 + 0.6 * Math.sin(time * 0.5), velocity: 0.12 * Math.cos(time * 0.5), torque: 2 + 0.4 * Math.sin(time), current: 1.2 + 0.25 * Math.sin(time * 1.3), temperature: 38 + 0.6 * Math.sin(time * 0.1), enabled: false, fault: false, t: time };
    return { t: time, force, emg, imu, motor };
  }
}

export const mockDataSource = new MockDataSource();
