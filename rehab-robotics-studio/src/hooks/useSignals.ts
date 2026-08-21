import { useSyncExternalStore } from 'react';
import { signalBus, type SignalSnapshot } from '../data/signalBus';

export function useSignals(): SignalSnapshot {
  return useSyncExternalStore(signalBus.subscribe, signalBus.getSnapshot, signalBus.getSnapshot);
}
