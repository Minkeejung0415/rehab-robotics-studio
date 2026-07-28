import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  createVisualizerRequestController,
  OPEN_SIM_TOOLBAR_ACTION_ORDER,
  visualizerFailureAlert,
} from '../common/Toast.js';

type CommandResult = { success: boolean; message: string };

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((settle) => {
    resolve = settle;
  });
  return { promise, resolve };
}

describe('Toolbar Open visualizer controller', () => {
  it('locks the exact OpenSim action order', () => {
    assert.deepEqual(
      [...OPEN_SIM_TOOLBAR_ACTION_ORDER],
      ['Calibrate', 'Clear cal', 'Open visualizer', 'Save'],
    );
  });

  it('shows pending state and suppresses duplicate pointer/keyboard activations', async () => {
    const request = deferred<CommandResult>();
    const busy: boolean[] = [];
    let calls = 0;
    const controller = createVisualizerRequestController({
      request: () => {
        calls += 1;
        return request.promise;
      },
      onBusyChange: (value) => busy.push(value),
      onFailure: () => assert.fail('success must not emit failure feedback'),
    });

    const pointer = controller.open();
    const enter = controller.open();
    const space = controller.open();
    assert.equal(controller.isPending(), true);
    assert.equal(calls, 1);
    assert.deepEqual(busy, [true]);
    assert.equal(await enter, null);
    assert.equal(await space, null);

    request.resolve({ success: true, message: 'accepted' });
    assert.deepEqual(await pointer, { success: true, message: 'accepted' });
    assert.equal(controller.isPending(), false);
    assert.deepEqual(busy, [true, false]);
  });

  it('normalizes one failure, restores settlement, and remains retryable', async () => {
    const results: CommandResult[] = [
      { success: false, message: 'simbody_visualizer_missing' },
      { success: true, message: 'accepted' },
    ];
    const failures: Array<{ reason: string; alert: string }> = [];
    let calls = 0;
    const controller = createVisualizerRequestController({
      request: async () => results[calls++],
      onBusyChange: () => {},
      onFailure: (reason, alert) => failures.push({ reason, alert }),
    });

    assert.deepEqual(await controller.open(), {
      success: false,
      message: 'Simbody visualizer missing',
    });
    assert.equal(controller.isPending(), false);
    assert.deepEqual(failures, [{
      reason: 'Simbody visualizer missing',
      alert: 'OpenSim visualizer could not open: Simbody visualizer missing. Check the OpenSim runtime, then retry.',
    }]);

    assert.deepEqual(await controller.open(), {
      success: true,
      message: 'accepted',
    });
    assert.equal(calls, 2);
    assert.equal(failures.length, 1);
  });

  it('contains rejected/raw reasons as normalized React text', async () => {
    assert.deepEqual(visualizerFailureAlert({ raw: 'payload' }), {
      reason: 'OpenSim visualizer could not open',
      message: 'OpenSim visualizer could not open: OpenSim visualizer could not open. Check the OpenSim runtime, then retry.',
    });

    const failures: string[] = [];
    const controller = createVisualizerRequestController({
      request: async () => {
        throw new Error('runtime_exception');
      },
      onBusyChange: () => {},
      onFailure: (reason) => failures.push(reason),
    });
    assert.deepEqual(await controller.open(), {
      success: false,
      message: 'Runtime exception',
    });
    assert.deepEqual(failures, ['Runtime exception']);
  });
});
