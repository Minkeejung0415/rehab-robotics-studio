# Phase 19 Dirty-Worktree Preservation Baseline

Recorded: `2026-07-28T19:39:46Z`  
Repository root: `C:/Users/justi/Documents/# Rehab Robotics GUI Prototype__Here's a complete, single-file React + TypeScript app implementing the LabVIEW`  
Branch: `master`  
HEAD: `b45e22dcb46e4599ddfa4123df8cee04ae5f3be9`

This is local, read-only preservation evidence created before any Phase 19 source edit.
It must remain untracked and unstaged. Existing tracked and untracked changes are
user-owned.

## Scope

The target list below is the union of `files_modified` in
`19-01-PLAN.md` through `19-07-PLAN.md`, plus
`rehab-robotics-studio/src/components/common/MiniChart.tsx`, which the blocking
checkpoint explicitly identifies as an overlapping Phase 19 target.

Exact-path status was collected with:

```powershell
git status --short --untracked-files=all -- <all paths listed below>
```

## Exact Pre-Execution Status

| Path | Exact status |
|---|---|
| `backend/rehab_robotics_bridge/opensim/ik_contracts.py` | tracked, clean |
| `backend/rehab_robotics_bridge/opensim_adapter.py` | tracked, clean |
| `backend/rehab_robotics_bridge/opensim_node.py` | tracked, clean |
| `backend/test/test_opensim_adapter.py` | tracked, clean |
| `backend/test/test_opensim_node.py` | tracked, clean |
| `rehab-robotics-studio/src/types/health.ts` | tracked, clean |
| `rehab-robotics-studio/src/types/signals.ts` | tracked, clean |
| `rehab-robotics-studio/src/data/liveKneeAngle.ts` | absent |
| `rehab-robotics-studio/src/data/liveKneeAngle.test.ts` | absent |
| `rehab-robotics-studio/src/data/DataSource.ts` | `??` untracked |
| `rehab-robotics-studio/src/data/RosbridgeDataSource.ts` | tracked, clean |
| `rehab-robotics-studio/src/data/RosbridgeDataSource.test.ts` | tracked, clean |
| `rehab-robotics-studio/src/data/appDataSource.ts` | tracked, clean |
| `rehab-robotics-studio/src/state/systemStore.ts` | `??` untracked |
| `rehab-robotics-studio/src/state/graphStore.ts` | tracked, clean |
| `rehab-robotics-studio/src/graph/blockDefinitions.ts` | tracked, clean |
| `rehab-robotics-studio/src/graph/mockExecutor.ts` | tracked, clean |
| `rehab-robotics-studio/src/graph/productKneeReadout.test.ts` | tracked, clean |
| `rehab-robotics-studio/src/data/signalBus.ts` | `??` untracked |
| `rehab-robotics-studio/src/components/chrome/Toolbar.tsx` | tracked, clean |
| `rehab-robotics-studio/src/components/chrome/Toolbar.test.ts` | absent |
| `rehab-robotics-studio/src/components/common/Toast.tsx` | tracked, clean |
| `rehab-robotics-studio/src/components/dashboard/HealthPanel.tsx` | tracked, clean |
| `rehab-robotics-studio/src/components/dashboard/HealthPanel.test.ts` | tracked, clean |
| `rehab-robotics-studio/scripts/phase19-qa.mjs` | absent |
| `rehab-robotics-studio/src/components/dashboard/MotorPanel.tsx` | `??` untracked |
| `rehab-robotics-studio/src/components/canvas/BlockNode.tsx` | tracked, clean |
| `rehab-robotics-studio/src/components/common/MiniChart.tsx` | `??` untracked |
| `rehab-robotics-studio/src/styles/app.css` | ` M` tracked, modified in worktree |
| `rehab-robotics-studio/package.json` | tracked, clean |
| `docs/stepesp-wireless-setup.md` | tracked, clean |

## Overlap Audit

The exact-path status contains only the six known overlaps:

- tracked dirty: `rehab-robotics-studio/src/styles/app.css`
- untracked: `rehab-robotics-studio/src/data/DataSource.ts`
- untracked: `rehab-robotics-studio/src/data/signalBus.ts`
- untracked: `rehab-robotics-studio/src/state/systemStore.ts`
- untracked: `rehab-robotics-studio/src/components/common/MiniChart.tsx`
- untracked: `rehab-robotics-studio/src/components/dashboard/MotorPanel.tsx`

Newly overlapping Phase 19 targets: **none**.

## Tracked Dirty Diff

Path: `rehab-robotics-studio/src/styles/app.css`  
Command: `git diff --no-ext-diff --binary -- rehab-robotics-studio/src/styles/app.css`

```diff
diff --git a/rehab-robotics-studio/src/styles/app.css b/rehab-robotics-studio/src/styles/app.css
index 60e0b2e..87145bc 100644
--- a/rehab-robotics-studio/src/styles/app.css
+++ b/rehab-robotics-studio/src/styles/app.css
@@ -518,6 +518,50 @@ select {
   padding-bottom: 6px;
 }
 
+.node-imu-controls {
+  display: grid;
+  grid-template-columns: 1fr;
+  gap: 5px;
+  margin: 0 8px 8px;
+  color: #8b969c;
+  font-family: ui-monospace, 'Cascadia Code', monospace;
+  font-size: 10px;
+}
+
+.node-imu-controls label {
+  display: grid;
+  grid-template-columns: 72px minmax(0, 1fr) auto;
+  align-items: center;
+  gap: 4px;
+}
+
+.node-imu-controls input,
+.node-imu-controls select {
+  width: 100%;
+  min-width: 0;
+  border: 1px solid #3b484e;
+  border-radius: 0;
+  background: #111416;
+  color: #dfe6ea;
+  font: inherit;
+  padding: 3px 4px;
+}
+
+.node-imu-controls select {
+  grid-column: 2 / span 2;
+}
+
+.node-imu-controls b {
+  color: #aab4ba;
+  font-weight: 400;
+}
+
+.node-imu-pending {
+  grid-column: 1 / -1;
+  color: #e0a64a;
+  font-style: normal;
+}
+
 .node-readout {
   margin: 5px 8px 8px;
   border: 1px solid #30383d;
@@ -662,6 +706,44 @@ select {
   background: #16191b;
 }
 
+.health-panel {
+  display: grid;
+  gap: 10px;
+}
+
+.health-grid {
+  display: grid;
+  grid-template-columns: repeat(2, minmax(0, 1fr));
+  gap: 8px;
+}
+
+.health-node {
+  display: grid;
+  gap: 4px;
+  border-left: 2px solid #3b484e;
+  padding-left: 8px;
+  color: #8b969c;
+  font-family: ui-monospace, 'Cascadia Code', monospace;
+  font-size: 10px;
+}
+
+.health-node strong { color: #dfe6ea; }
+.health-state.ok { color: #46c47a; }
+.health-state.warn { color: #e0a64a; }
+.health-stale { color: #ec5a5a; font-weight: 600; }
+
+.recording-health {
+  border-top: 1px solid #23292d;
+  padding-top: 9px;
+}
+
+.recording-health .dash-head { margin-bottom: 6px; }
+.recording-recording { color: #ec5a5a; }
+.recording-finalizing { color: #e0a64a; }
+.recording-finalized { color: #46c47a; }
+.recording-error, .health-error { color: #ec5a5a !important; }
+.health-note { margin: 8px 0 0; color: #8b969c; font-size: 11px; }
+
 .dash-head {
   display: flex;
   justify-content: space-between;
```

## Untracked Overlap Snapshots

### `rehab-robotics-studio/src/data/DataSource.ts`

- SHA-256: `96e43a2a3d933b737bb42035817b0911df5080cb49d08e6701118d43df4d23c2`
- Bytes: `1021`
- Lines: `27`

```typescript
import type { Frame } from '../types/signals';

/**
 * Abstraction over a stream of acquisition frames.
 *
 * `MockDataSource` implements this today. The whole point of the interface is
 * that a future `RosbridgeDataSource` / `RedPitayaDataSource` can implement the
 * exact same contract and be dropped into `signalBus` with no UI changes.
 */
export interface DataSource {
  /** Begin streaming at the given conceptual sample rate (Hz). */
  start(rateHz: number): void;
  /** Stop streaming and release any timers/sockets. */
  stop(): void;
  /** Temporarily halt emission without tearing down. */
  pause(): void;
  /** Resume after pause. */
  resume(): void;
  /** Change the conceptual sample rate while running. */
  setSampleRate(rateHz: number): void;
  /**
   * Subscribe to frames. Returns an unsubscribe function.
   * Frames may arrive at the data rate — consumers must NOT assume this maps
   * to React render rate (see `signalBus`).
   */
  subscribe(callback: (frame: Frame) => void): () => void;
}
```

### `rehab-robotics-studio/src/data/signalBus.ts`

- SHA-256: `8c6c2d21a2bd21f54e5e9cc601969097de1d0afaa17b47d1949e755eb2f855f8`
- Bytes: `4054`
- Lines: `151`

```typescript
import type { Frame, MotorState } from '../types/signals';
import { appDataSource } from './appDataSource';
import { runMockExecutor, type ExecMemory } from '../graph/mockExecutor';
import { useGraphStore } from '../state/graphStore';

/**
 * Fixed-capacity ring buffer of numbers, kept as a plain array window.
 */
class RingBuffer {
  private data: number[];
  constructor(private cap: number) {
    this.data = new Array(cap).fill(0);
  }
  push(v: number): void {
    this.data.push(v);
    if (this.data.length > this.cap) this.data.shift();
  }
  toArray(): number[] {
    return this.data.slice();
  }
}

/** Immutable snapshot React reads via useSyncExternalStore. */
export interface SignalSnapshot {
  t: number;
  forceRaw: number;
  forceProcessed: number;
  emgRaw: number;
  emgEnvelope: number;
  kneeAngle: number;
  motor: MotorState;
  forceSeries: number[];
  emgSeries: number[];
  kneeSeries: number[];
}

const emptyMotor: MotorState = {
  position: 0,
  velocity: 0,
  torque: 0,
  current: 0,
  temperature: 0,
  enabled: false,
  fault: false,
  t: 0,
};

function emptySnapshot(): SignalSnapshot {
  return {
    t: 0,
    forceRaw: 0,
    forceProcessed: 0,
    emgRaw: 0,
    emgEnvelope: 0,
    kneeAngle: 0,
    motor: emptyMotor,
    forceSeries: new Array(240).fill(0),
    emgSeries: new Array(240).fill(0),
    kneeSeries: new Array(240).fill(0),
  };
}

/**
 * The SignalBus is the seam between the (fast) data source and (slow) React UI.
 *
 *  - `ingest(frame)` runs at the DATA rate: it executes the graph, fills ring
 *    buffers, and updates `latest`. It does NOT touch React.
 *  - a requestAnimationFrame loop publishes a fresh `snapshot` and notifies
 *    React listeners at most ~30 fps. This is how we avoid re-rendering React
 *    1000×/second.
 *
 * The application source selects ROS data by default and mock data as a local fallback.
 */
class SignalBus {
  private forceBuf = new RingBuffer(240);
  private emgBuf = new RingBuffer(240);
  private kneeBuf = new RingBuffer(240);
  private baseline = 0;
  private mem: ExecMemory = {};

  private latest: SignalSnapshot = emptySnapshot();
  private snapshot: SignalSnapshot = this.latest;
  private listeners = new Set<() => void>();
  private dirty = false;
  private lastNotify = 0;

  constructor() {
    appDataSource.subscribe((f) => this.ingest(f));
    if (typeof requestAnimationFrame !== 'undefined') {
      requestAnimationFrame(this.loop);
    }
  }

  /** Set the current raw force as the new zero (Tare). */
  tare(): void {
    this.baseline = this.latest.forceRaw;
  }

  private ingest(frame: Frame): void {
    const { nodes, edges } = useGraphStore.getState();
    const out = runMockExecutor(nodes, edges, frame, this.mem);

    const forceProcessed = (out.force ?? frame.force.fz) - this.baseline;
    const emgEnvelope = out.emg ?? frame.emg.envelope;
    const kneeAngle = out.knee ?? 0;

    this.forceBuf.push(forceProcessed);
    this.emgBuf.push(emgEnvelope);
    this.kneeBuf.push(kneeAngle);

    this.latest = {
      t: frame.t,
      forceRaw: frame.force.fz,
      forceProcessed,
      emgRaw: frame.emg.raw,
      emgEnvelope,
      kneeAngle,
      motor: frame.motor,
      forceSeries: this.latest.forceSeries,
      emgSeries: this.latest.emgSeries,
      kneeSeries: this.latest.kneeSeries,
    };
    this.dirty = true;
  }

  private loop = (ts: number): void => {
    if (this.dirty && ts - this.lastNotify > 33) {
      this.lastNotify = ts;
      this.dirty = false;
      this.snapshot = {
        ...this.latest,
        forceSeries: this.forceBuf.toArray(),
        emgSeries: this.emgBuf.toArray(),
        kneeSeries: this.kneeBuf.toArray(),
      };
      this.listeners.forEach((l) => l());
    }
    requestAnimationFrame(this.loop);
  };

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  getSnapshot = (): SignalSnapshot => this.snapshot;
}

export const signalBus = new SignalBus();
```

### `rehab-robotics-studio/src/state/systemStore.ts`

- SHA-256: `c98f29466c96f85a198d1aedd67018b0acb1149ea923e2c48dd2b29ae1719a24`
- Bytes: `3516`
- Lines: `96`

```typescript
import { create } from 'zustand';
import type { SystemStatus, LogEntry, LogLevel, IndicatorLevel } from '../types/system';
import type { OpenSimStatusSnapshot, PairHealthSnapshot } from '../types/health';

function timestamp(): string {
  const d = new Date();
  const pad = (x: number, l = 2) => String(x).padStart(l, '0');
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${pad(d.getMilliseconds(), 3)}`;
}

let logSeq = 0;

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

  addLog(level: LogLevel, message: string): void;
  clearLogs(): void;
  setMotor(value: string, level: IndicatorLevel): void;
  setRosConnected(connected: boolean): void;
  setEspStreamActive(active: boolean): void;
  setRecording(on: boolean): void;
  setFault(active: boolean, message?: string): void;
  setPairHealth(health: PairHealthSnapshot): void;
  setOpenSimStatus(status: OpenSimStatusSnapshot): void;
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

  addLog: (level, message) =>
    set((s) => ({
      logs: [...s.logs, { id: `l${logSeq++}`, t: timestamp(), level, message }].slice(-300),
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
  setOpenSimStatus: (openSimStatus) => set({ openSimStatus }),
}));
```

### `rehab-robotics-studio/src/components/common/MiniChart.tsx`

- SHA-256: `ed905aac1bf4c88ae9bf4097f252a3303cdea932bde09589da3d629ab705d13e`
- Bytes: `1575`
- Lines: `58`

```tsx
import { useEffect, useRef } from 'react';

interface Props {
  data: number[];
  color: string;
  height?: number;
  /** Logical canvas width; the element still stretches to its container. */
  width?: number;
  fill?: boolean;
}

/**
 * Lightweight scrolling line chart on a <canvas>. Redraws only when `data`
 * changes (which happens at the throttled snapshot rate, not the data rate).
 */
export function MiniChart({ data, color, height = 64, width = 260, fill = true }: Props) {
  const ref = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const cv = ref.current;
    if (!cv) return;
    const ctx = cv.getContext('2d');
    if (!ctx) return;
    const W = cv.width;
    const H = cv.height;
    ctx.clearRect(0, 0, W, H);
    if (data.length < 2) return;

    let mn = Math.min(...data);
    let mx = Math.max(...data);
    if (mx - mn < 1e-6) mx = mn + 1;
    const pad = (mx - mn) * 0.18;
    mn -= pad;
    mx += pad;

    ctx.beginPath();
    for (let i = 0; i < data.length; i++) {
      const x = (i / (data.length - 1)) * W;
      const y = H - ((data[i] - mn) / (mx - mn)) * H;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.4;
    ctx.lineJoin = 'round';
    ctx.stroke();

    if (fill) {
      ctx.lineTo(W, H);
      ctx.lineTo(0, H);
      ctx.closePath();
      ctx.fillStyle = color + '22';
      ctx.fill();
    }
  }, [data, color, fill]);

  return <canvas ref={ref} width={width} height={height} style={{ width: '100%', height, display: 'block' }} />;
}
```

### `rehab-robotics-studio/src/components/dashboard/MotorPanel.tsx`

- SHA-256: `924880ba29e61c64d662ce6eea5ae89bf9f9c320ed363b9fc87002fa236023fb`
- Bytes: `1160`
- Lines: `27`

```tsx
import { signalColor } from '../../theme/tokens';
import { useSignals } from '../../hooks/useSignals';
import { MiniChart } from '../common/MiniChart';

export function MotorPanel() {
  const { motor, kneeAngle, kneeSeries } = useSignals();

  return (
    <section className="dash-panel">
      <div className="dash-head">
        <h3>Motor / Joint</h3>
        <span className={`motor-pill ${motor.fault ? 'fault' : motor.enabled ? 'enabled' : ''}`}>
          {motor.fault ? 'FAULT' : motor.enabled ? 'ENABLED' : 'DISABLED'}
        </span>
      </div>
      <div className="readout-grid">
        <span>Knee</span><strong>{kneeAngle.toFixed(1)} deg</strong>
        <span>Position</span><strong>{motor.position.toFixed(2)} rad</strong>
        <span>Velocity</span><strong>{motor.velocity.toFixed(2)} rad/s</strong>
        <span>Torque</span><strong>{motor.torque.toFixed(2)} Nm</strong>
        <span>Current</span><strong>{motor.current.toFixed(2)} A</strong>
        <span>Temp</span><strong>{motor.temperature.toFixed(1)} C</strong>
      </div>
      <MiniChart data={kneeSeries} color={signalColor.joint_state} height={48} />
    </section>
  );
}
```

## Preservation and Staging Policy

For every later Phase 19 task:

1. Re-run exact-path `git status --short -- <task paths>` and
   `git diff --no-ext-diff --binary -- <tracked dirty path>` before editing.
2. Recompute SHA-256, bytes, and line count for any untracked overlap and compare it
   with this baseline before editing.
3. Apply narrow patches on top of the recorded content. Do not replace, recreate,
   normalize, or broadly reformat overlapping files.
4. Compare the post-edit file/diff with this baseline and preserve every recorded
   user-owned hunk.
5. Stage only the explicitly listed task paths using
   `git add -- <exact path> [<exact path> ...]`.
6. Never use `git add .`, `git add -A`, broad globs, stash, reset, checkout, clean,
   or replacement commands.
7. Never stage or commit this local baseline evidence file.
