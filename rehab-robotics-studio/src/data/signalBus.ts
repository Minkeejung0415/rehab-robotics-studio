import type { Frame, MotorState } from '../types/signals';
import type { LiveKneeAngleSnapshot } from '../types/health';
import { appDataSource } from './appDataSource';
import { runMockExecutor, type ExecMemory } from '../graph/mockExecutor';
import { useGraphStore } from '../state/graphStore';
import { useSystemStore } from '../state/systemStore';

/**
 * Fixed-capacity ring buffer of numbers, kept as a plain array window.
 */
class RingBuffer {
  private data: number[];
  constructor(private cap: number, prefill = true) {
    this.data = prefill ? new Array(cap).fill(0) : [];
  }
  push(v: number): void {
    this.data.push(v);
    if (this.data.length > this.cap) this.data.shift();
  }
  clear(): void {
    this.data = [];
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
  kneeAngle: number | null;
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
    kneeAngle: null,
    motor: emptyMotor,
    forceSeries: new Array(240).fill(0),
    emgSeries: new Array(240).fill(0),
    kneeSeries: [],
  };
}

interface SignalBusOptions {
  subscribeFrames?: (callback: (frame: Frame) => void) => () => void;
  getGraph?: () => Pick<ReturnType<typeof useGraphStore.getState>, 'nodes' | 'edges'>;
  getLiveKneeAngle?: () => LiveKneeAngleSnapshot;
  subscribeLiveKneeAngle?: (
    callback: (snapshot: LiveKneeAngleSnapshot) => void,
  ) => () => void;
  requestFrame?: ((callback: FrameRequestCallback) => number) | null;
  cancelFrame?: ((handle: number) => void) | null;
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
export class SignalBus {
  private forceBuf = new RingBuffer(240);
  private emgBuf = new RingBuffer(240);
  private kneeBuf = new RingBuffer(240, false);
  private baseline = 0;
  private mem: ExecMemory = {};
  private liveKneeAngleDeg: number | null;
  private readonly getGraph: NonNullable<SignalBusOptions['getGraph']>;
  private readonly requestFrame: NonNullable<SignalBusOptions['requestFrame']> | null;
  private readonly cancelFrame: NonNullable<SignalBusOptions['cancelFrame']> | null;
  private readonly unsubscribers: Array<() => void> = [];
  private frameHandle: number | null = null;
  private disposed = false;

  private latest: SignalSnapshot = emptySnapshot();
  private snapshot: SignalSnapshot = this.latest;
  private listeners = new Set<() => void>();
  private dirty = false;
  private lastNotify = 0;

  constructor(options: SignalBusOptions = {}) {
    const getLiveKneeAngle = options.getLiveKneeAngle
      ?? (() => useSystemStore.getState().liveKneeAngle);
    const subscribeLiveKneeAngle = options.subscribeLiveKneeAngle
      ?? ((callback) => useSystemStore.subscribe((state, previous) => {
        if (state.liveKneeAngle !== previous.liveKneeAngle) {
          callback(state.liveKneeAngle);
        }
      }));

    this.getGraph = options.getGraph ?? (() => useGraphStore.getState());
    const nativeRequestFrame = globalThis.requestAnimationFrame;
    const nativeCancelFrame = globalThis.cancelAnimationFrame;
    this.requestFrame = options.requestFrame === undefined
      ? (
          typeof nativeRequestFrame === 'function'
            ? (callback) => nativeRequestFrame.call(globalThis, callback)
            : null
        )
      : options.requestFrame;
    this.cancelFrame = options.cancelFrame === undefined
      ? (
          typeof nativeCancelFrame === 'function'
            ? (handle) => nativeCancelFrame.call(globalThis, handle)
            : null
        )
      : options.cancelFrame;
    this.liveKneeAngleDeg = this.liveValue(getLiveKneeAngle());
    this.unsubscribers.push(
      (options.subscribeFrames ?? ((callback) => appDataSource.subscribe(callback)))(
        (frame) => this.ingest(frame),
      ),
      subscribeLiveKneeAngle((snapshot) => this.setLiveKneeAngle(snapshot)),
    );

    if (this.requestFrame) {
      this.frameHandle = this.requestFrame(this.loop);
    }
  }

  /** Set the current raw force as the new zero (Tare). */
  tare(): void {
    this.baseline = this.latest.forceRaw;
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    if (this.frameHandle !== null && this.cancelFrame) {
      this.cancelFrame(this.frameHandle);
    }
    this.frameHandle = null;
    this.unsubscribers.splice(0).forEach((unsubscribe) => unsubscribe());
    this.listeners.clear();
  }

  private liveValue(snapshot: LiveKneeAngleSnapshot): number | null {
    return snapshot.state === 'live' && Number.isFinite(snapshot.valueDeg)
      ? snapshot.valueDeg
      : null;
  }

  private setLiveKneeAngle(snapshot: LiveKneeAngleSnapshot): void {
    const wasLive = this.liveKneeAngleDeg !== null;
    this.liveKneeAngleDeg = this.liveValue(snapshot);
    if (this.liveKneeAngleDeg !== null) {
      if (!wasLive) this.kneeBuf.clear();
      return;
    }

    const changed = this.latest.kneeAngle !== null
      || this.snapshot.kneeAngle !== null
      || this.latest.kneeSeries.length > 0
      || this.snapshot.kneeSeries.length > 0;
    this.kneeBuf.clear();
    this.latest = { ...this.latest, kneeAngle: null, kneeSeries: [] };
    this.snapshot = { ...this.snapshot, kneeAngle: null, kneeSeries: [] };
    if (changed) this.listeners.forEach((listener) => listener());
  }

  private ingest(frame: Frame): void {
    const { nodes, edges } = this.getGraph();
    // Always overwrite a DataSource-supplied value. Only the independently
    // derived store snapshot may inject the official product field.
    const productFrame: Frame = {
      ...frame,
      openSimKneeAngleDeg: this.liveKneeAngleDeg,
    };
    const out = runMockExecutor(nodes, edges, productFrame, this.mem);

    const forceProcessed = (out.force ?? frame.force.fz) - this.baseline;
    const emgEnvelope = out.emg ?? frame.emg.envelope;
    const kneeAngle = (
      this.liveKneeAngleDeg !== null
      && typeof out.knee === 'number'
      && Number.isFinite(out.knee)
      && Object.is(out.knee, this.liveKneeAngleDeg)
    )
      ? out.knee
      : null;

    this.forceBuf.push(forceProcessed);
    this.emgBuf.push(emgEnvelope);
    if (kneeAngle === null) this.kneeBuf.clear();
    else this.kneeBuf.push(kneeAngle);

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
      kneeSeries: kneeAngle === null ? [] : this.latest.kneeSeries,
    };
    this.dirty = true;
    if (!this.requestFrame) this.publish();
  }

  private publish(): void {
    this.dirty = false;
    this.snapshot = {
      ...this.latest,
      forceSeries: this.forceBuf.toArray(),
      emgSeries: this.emgBuf.toArray(),
      kneeSeries: this.kneeBuf.toArray(),
    };
    this.listeners.forEach((listener) => listener());
  }

  private loop = (ts: number): void => {
    if (this.disposed) return;
    if (this.dirty && ts - this.lastNotify > 33) {
      this.lastNotify = ts;
      this.publish();
    }
    this.frameHandle = this.requestFrame?.(this.loop) ?? null;
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
