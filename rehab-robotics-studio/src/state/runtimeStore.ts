import { create } from 'zustand';
import type { RuntimeState, LogLevel } from '../types/system';
import { mockDataSource } from '../data/MockDataSource';
import { useGraphStore } from './graphStore';
import { useSystemStore } from './systemStore';
import { signalBus } from '../data/signalBus';

/**
 * Allowed transitions (per spec):
 *   idle      → running
 *   running   → paused | idle | estopped | fault
 *   paused    → running | idle | estopped | fault
 *   estopped  → idle   (only via explicit reset)
 *   fault     → idle   (only via explicit reset)
 *   any       → estopped | fault
 */
const TRANSITIONS: Record<RuntimeState, RuntimeState[]> = {
  idle: ['running', 'estopped', 'fault'],
  running: ['paused', 'idle', 'estopped', 'fault'],
  paused: ['running', 'idle', 'estopped', 'fault'],
  estopped: ['idle'],
  fault: ['idle'],
};

function can(from: RuntimeState, to: RuntimeState): boolean {
  return TRANSITIONS[from].includes(to);
}

interface RuntimeStore {
  state: RuntimeState;
  sampleRate: number;

  run(): void;
  pause(): void;
  resume(): void;
  stop(): void;
  estop(): void;
  raiseFault(message: string): void;
  reset(): void;
  setSampleRate(rateHz: number): void;
  tare(): void;
}

export const useRuntimeStore = create<RuntimeStore>((set, get) => {
  const log = (level: LogLevel, msg: string) => useSystemStore.getState().addLog(level, msg);

  return {
    state: 'idle',
    sampleRate: 1000,

    run: () => {
      const { state, sampleRate } = get();
      // run from idle; resume from paused (Run button handles both)
      if (state === 'paused') {
        get().resume();
        return;
      }
      if (!can(state, 'running')) {
        log('WARN', `Cannot run from state "${state}"`);
        return;
      }
      mockDataSource.start(sampleRate);
      set({ state: 'running' });
      useGraphStore.getState().setAllNodeStatuses('running');
      log('INFO', 'Execution started');
    },

    pause: () => {
      const { state } = get();
      if (!can(state, 'paused')) return;
      mockDataSource.pause();
      set({ state: 'paused' });
      log('INFO', 'Execution paused');
    },

    resume: () => {
      const { state } = get();
      if (state !== 'paused') return;
      mockDataSource.resume();
      set({ state: 'running' });
      useGraphStore.getState().setAllNodeStatuses('running');
      log('INFO', 'Execution resumed');
    },

    stop: () => {
      const { state } = get();
      if (!can(state, 'idle')) return;
      mockDataSource.stop();
      set({ state: 'idle' });
      useGraphStore.getState().setAllNodeStatuses('idle');
      log('INFO', 'Execution stopped');
    },

    estop: () => {
      mockDataSource.stop();
      set({ state: 'estopped' });
      useGraphStore.getState().setAllNodeStatuses('idle');
      useSystemStore.getState().setMotor('ESTOP', 'fault');
      log('SAFETY', 'EMERGENCY STOP ENGAGED — motor driver disabled');
    },

    raiseFault: (message) => {
      mockDataSource.stop();
      set({ state: 'fault' });
      useGraphStore.getState().setAllNodeStatuses('idle');
      useSystemStore.getState().setFault(true, 'FAULT');
      log('ERROR', `FAULT: ${message}`);
    },

    reset: () => {
      const { state } = get();
      if (state !== 'estopped' && state !== 'fault') {
        log('WARN', 'Reset only allowed from E-Stop or Fault');
        return;
      }
      set({ state: 'idle' });
      useGraphStore.getState().setAllNodeStatuses('idle');
      useSystemStore.getState().setMotor('Disabled', 'idle');
      useSystemStore.getState().setFault(false);
      log('SAFETY', `Reset from ${state} — system re-armed`);
    },

    setSampleRate: (rateHz) => {
      set({ sampleRate: rateHz });
      mockDataSource.setSampleRate(rateHz);
      log('INFO', `Sample rate set to ${rateHz} Hz`);
    },

    tare: () => {
      signalBus.tare();
      log('INFO', 'Load cell tared — force baseline set to 0.0 N');
    },
  };
});
