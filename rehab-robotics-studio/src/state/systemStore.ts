import { create } from 'zustand';
import type { SystemStatus, LogEntry, LogLevel, IndicatorLevel } from '../types/system';
import type {
  LiveKneeAngleSnapshot,
  OpenSimIkStatusSnapshot,
  OpenSimJointStateSnapshot,
  OpenSimStatusSnapshot,
  OpenSimVisualizerRequestSnapshot,
  PairHealthSnapshot,
} from '../types/health';

function timestamp(): string {
  const d = new Date();
  const pad = (x: number, l = 2) => String(x).padStart(l, '0');
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${pad(d.getMilliseconds(), 3)}`;
}

let logSeq = 0;
let lastAngleLogSignature = '';
let lastCalibrationLogSignature = '';
let lastIkLogSignature = '';
let lastVisualizerLogSignature = '';

function appendLog(logs: LogEntry[], level: LogLevel, message: string): LogEntry[] {
  return [...logs, { id: `l${logSeq++}`, t: timestamp(), level, message }].slice(-300);
}

function transitionReason(reason: string): string {
  return reason ? ` - ${reason}` : '';
}

const INITIAL_STATUS: SystemStatus = {
  ros: { label: 'ROS', value: 'Awaiting bridge', level: 'idle' },
  jetson: { label: 'Jetson', value: 'Not connected', level: 'idle' },
  redPitaya: { label: 'ESP32 stream', value: 'Awaiting data', level: 'idle' },
  motor: { label: 'Motor', value: 'Disabled', level: 'idle' },
  recording: { label: 'Recording', value: 'Off', level: 'idle' },
  fault: { label: 'Fault', value: 'Clear', level: 'ok' },
};

interface SystemStore {
  status: SystemStatus;
  logs: LogEntry[];
  pairHealth: PairHealthSnapshot | null;
  openSimStatus: OpenSimStatusSnapshot | null;
  openSimIkStatus: OpenSimIkStatusSnapshot | null;
  openSimJointState: OpenSimJointStateSnapshot | null;
  liveKneeAngle: LiveKneeAngleSnapshot;
  openSimVisualizerRequest: OpenSimVisualizerRequestSnapshot;

  addLog(level: LogLevel, message: string): void;
  clearLogs(): void;
  setMotor(value: string, level: IndicatorLevel): void;
  setRosConnected(connected: boolean): void;
  setEspStreamActive(active: boolean): void;
  setRecording(on: boolean): void;
  setFault(active: boolean, message?: string): void;
  setPairHealth(health: PairHealthSnapshot): void;
  setOpenSimStatus(status: OpenSimStatusSnapshot): void;
  setOpenSimIkStatus(status: OpenSimIkStatusSnapshot): void;
  setOpenSimJointState(jointState: OpenSimJointStateSnapshot | null): void;
  setLiveKneeAngle(snapshot: LiveKneeAngleSnapshot): void;
  setOpenSimVisualizerRequest(snapshot: OpenSimVisualizerRequestSnapshot): void;
}

export const useSystemStore = create<SystemStore>((set) => ({
  status: INITIAL_STATUS,
  logs: [
    { id: `l${logSeq++}`, t: timestamp(), level: 'INFO', message: 'ROS bridge connected (mock)' },
    { id: `l${logSeq++}`, t: timestamp(), level: 'INFO', message: 'Jetson Orin online (mock)' },
    { id: `l${logSeq++}`, t: timestamp(), level: 'INFO', message: 'Red Pitaya streaming (mock)' },
    { id: `l${logSeq++}`, t: timestamp(), level: 'INFO', message: 'Graph loaded — 11 blocks' },
    { id: `l${logSeq++}`, t: timestamp(), level: 'WARN', message: 'Motor driver disabled — arm to enable' },
    { id: `l${logSeq++}`, t: timestamp(), level: 'INFO', message: 'Ready' },
  ],
  pairHealth: null,
  openSimStatus: null,
  openSimIkStatus: null,
  openSimJointState: null,
  liveKneeAngle: {
    state: 'waiting',
    valueDeg: null,
    reason: 'Waiting for calibrated IK',
  },
  openSimVisualizerRequest: { state: 'idle', reason: '' },

  addLog: (level, message) =>
    set((s) => ({
      logs: appendLog(s.logs, level, message),
    })),

  clearLogs: () => set({ logs: [] }),

  setMotor: (value, level) =>
    set((s) => ({ status: { ...s.status, motor: { ...s.status.motor, value, level } } })),

  setRosConnected: (connected) =>
    set((s) => ({
      status: {
        ...s.status,
        ros: { ...s.status.ros, value: connected ? 'Connected' : 'Unavailable', level: connected ? 'ok' : 'warn' },
      },
    })),

  setEspStreamActive: (active) =>
    set((s) => ({
      status: {
        ...s.status,
        redPitaya: { ...s.status.redPitaya, value: active ? 'Streaming' : 'Awaiting data', level: active ? 'ok' : 'idle' },
      },
    })),

  setRecording: (on) =>
    set((s) => ({
      status: {
        ...s.status,
        recording: { ...s.status.recording, value: on ? 'On' : 'Off', level: on ? 'fault' : 'idle' },
      },
    })),

  setFault: (active, message) =>
    set((s) => ({
      status: {
        ...s.status,
        fault: { ...s.status.fault, value: active ? (message ?? 'FAULT') : 'Clear', level: active ? 'fault' : 'ok' },
      },
    })),

  setPairHealth: (pairHealth) => set({ pairHealth }),
  setOpenSimStatus: (openSimStatus) =>
    set((s) => {
      let logs = s.logs;
      const calibrationState = openSimStatus.calibration?.state ?? 'UNKNOWN';
      const calibrationReason = openSimStatus.calibration?.reason ?? '';
      const calibrationSignature = `${calibrationState}\u0000${calibrationReason}`;
      if (calibrationSignature !== lastCalibrationLogSignature) {
        lastCalibrationLogSignature = calibrationSignature;
        logs = appendLog(
          logs,
          calibrationState === 'FAILED' ? 'ERROR' : calibrationState === 'CAPTURING' ? 'WARN' : 'INFO',
          `OpenSim calibration ${calibrationState}${transitionReason(calibrationReason)}`,
        );
      }

      const visualizationState = openSimStatus.visualization?.state?.toLowerCase() ?? 'waiting';
      const visualizationReason = openSimStatus.visualization?.reason ?? '';
      const visualizationSignature = `${visualizationState}\u0000${visualizationReason}`;
      if (visualizationSignature !== lastVisualizerLogSignature) {
        lastVisualizerLogSignature = visualizationSignature;
        logs = appendLog(
          logs,
          visualizationState === 'failed' || visualizationState === 'unavailable' ? 'ERROR' : 'INFO',
          `OpenSim visualizer ${visualizationState}${transitionReason(visualizationReason)}`,
        );
      }

      const backendAccepted = visualizationState === 'opening' || visualizationState === 'open';
      return {
        logs,
        openSimStatus,
        openSimVisualizerRequest: backendAccepted
          ? { state: 'idle', reason: '' }
          : s.openSimVisualizerRequest,
      };
    }),

  setOpenSimIkStatus: (openSimIkStatus) =>
    set((s) => {
      const state = openSimIkStatus.solution_valid ? 'VALID' : 'INVALID';
      const reason = openSimIkStatus.reason ?? '';
      const signature = `${state}\u0000${reason}`;
      if (signature === lastIkLogSignature) return { openSimIkStatus };
      lastIkLogSignature = signature;
      return {
        openSimIkStatus,
        logs: appendLog(
          s.logs,
          openSimIkStatus.solution_valid ? 'INFO' : 'WARN',
          `OpenSim IK ${state}${transitionReason(reason)}`,
        ),
      };
    }),

  setOpenSimJointState: (openSimJointState) => set({ openSimJointState }),

  setLiveKneeAngle: (liveKneeAngle) =>
    set((s) => {
      const signature = `${liveKneeAngle.state}\u0000${liveKneeAngle.reason}`;
      if (signature === lastAngleLogSignature) return { liveKneeAngle };
      lastAngleLogSignature = signature;
      const label = liveKneeAngle.state.toUpperCase();
      const level: LogLevel = liveKneeAngle.state === 'invalid' || liveKneeAngle.state === 'stale'
        ? 'WARN'
        : 'INFO';
      return {
        liveKneeAngle,
        logs: appendLog(
          s.logs,
          level,
          `OpenSim knee angle ${label}${transitionReason(liveKneeAngle.reason)}`,
        ),
      };
    }),

  setOpenSimVisualizerRequest: (openSimVisualizerRequest) =>
    set((s) => {
      if (openSimVisualizerRequest.state === 'idle') return { openSimVisualizerRequest };
      const signature = `${openSimVisualizerRequest.state}\u0000${openSimVisualizerRequest.reason}`;
      if (signature === lastVisualizerLogSignature) return { openSimVisualizerRequest };
      lastVisualizerLogSignature = signature;
      return {
        openSimVisualizerRequest,
        logs: appendLog(
          s.logs,
          openSimVisualizerRequest.state === 'failed' ? 'ERROR' : 'INFO',
          openSimVisualizerRequest.state === 'failed'
            ? `OpenSim visualizer failed${transitionReason(openSimVisualizerRequest.reason)}`
            : 'OpenSim visualizer opening',
        ),
      };
    }),
}));
