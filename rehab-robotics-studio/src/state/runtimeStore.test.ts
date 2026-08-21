import test from 'node:test';
import assert from 'node:assert/strict';
import { useRuntimeStore } from './runtimeStore';
import { appDataSource } from '../data/appDataSource';

test('Run starts the selected application data source, not a mock-only bypass', () => {
  const originalStart = appDataSource.start;
  const originalStop = appDataSource.stop;
  let startedAt: number | null = null;
  let stopped = false;
  appDataSource.start = (rateHz) => { startedAt = rateHz; };
  appDataSource.stop = () => { stopped = true; };
  try {
    useRuntimeStore.setState({ state: 'idle', sampleRate: 100 });
    useRuntimeStore.getState().run();
    assert.equal(startedAt, 100);
    useRuntimeStore.getState().stop();
    assert.equal(stopped, true);
  } finally {
    appDataSource.start = originalStart;
    appDataSource.stop = originalStop;
    useRuntimeStore.setState({ state: 'idle' });
  }
});
