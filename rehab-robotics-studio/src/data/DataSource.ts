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

/**
 * Narrow OpenSim control surface exposed by live data sources.
 *
 * Browser callers can request only the fixed backend-owned visualizer action;
 * no command, path, or process input crosses this boundary.
 */
export interface OpenSimDataSource {
  openVisualizer(): Promise<{ success: boolean; message: string }>;
}
