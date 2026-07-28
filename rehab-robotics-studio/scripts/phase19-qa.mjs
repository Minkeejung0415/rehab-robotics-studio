import { spawn } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const mode = process.argv.includes('--contract-check')
  ? 'contract-check'
  : process.argv.includes('--toolbar-only')
    ? 'toolbar-only'
    : 'full';

const CONTRACT = Object.freeze({
  subscriptions: Object.freeze({
    '/opensim/status': 'std_msgs/msg/String',
    '/opensim/ik_status': 'std_msgs/msg/String',
    '/opensim/joint_states': 'sensor_msgs/msg/JointState',
  }),
  visualizerService: '/opensim/visualizer/open',
  calibrationService: '/opensim/calibration/capture',
  triggerType: 'std_srvs/srv/Trigger',
  scenarios: Object.freeze([
    'toolbar-order',
    'visualizer-pending-duplicate-suppression',
    'visualizer-failure-persistence-retry-success',
    'standing-calibration',
    'invalid-em-dash',
    'reordered-pi-over-two-all-displays',
    'stale-at-2001-ms',
    'new-series-recovery',
    'malformed-envelope-isolation',
    'obsolete-session-reply-message-close-rejection',
  ]),
  cleanup: Object.freeze(['browser.close', 'preview.kill']),
  failureFormat: 'machine-readable-json',
});

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function printResult(result) {
  console.log(JSON.stringify(result, null, 2));
}

function runContractCheck() {
  const startedAt = Date.now();
  const source = readFileSync(new URL(import.meta.url), 'utf8');
  const packageJson = JSON.parse(readFileSync(resolve('package.json'), 'utf8'));
  const checks = [];
  const check = (name, condition) => {
    assert(condition, `Contract check failed: ${name}`);
    checks.push(name);
  };

  check('three typed OpenSim subscriptions', Object.keys(CONTRACT.subscriptions).length === 3);
  for (const [topic, type] of Object.entries(CONTRACT.subscriptions)) {
    check(`subscription ${topic} ${type}`, source.includes(topic) && source.includes(type));
  }
  check(
    'fixed argument-free visualizer Trigger',
    source.includes(CONTRACT.visualizerService)
      && source.includes(CONTRACT.triggerType)
      && source.includes('assertTriggerCall(visualizerCall'),
  );
  check(
    'standing calibration Trigger',
    source.includes(CONTRACT.calibrationService)
      && source.includes('assertTriggerCall(calibrationCall'),
  );
  for (const scenario of CONTRACT.scenarios) {
    check(`scenario ${scenario}`, source.includes(`markScenario('${scenario}')`));
  }
  check(
    'bounded lifecycle cleanup',
    source.includes('await browser?.close()')
      && source.includes('server?.kill()')
      && source.includes('waitForServer(timeoutMs = 15_000)')
      && source.includes('chromium.launch({ headless: true, timeout: 15_000 })'),
  );
  check(
    'machine-readable failure handling',
    source.includes("ok: false")
      && source.includes("mode")
      && source.includes("process.exitCode = 1"),
  );
  check(
    'package test:phase19 builds then runs default QA',
    packageJson.scripts?.['test:phase19']
      === 'npm run build && node scripts/phase19-qa.mjs',
  );

  printResult({
    ok: true,
    mode,
    elapsedMs: Date.now() - startedAt,
    checks,
    browserStarted: false,
    previewStarted: false,
    networkUsed: false,
  });
}

if (mode === 'contract-check') {
  try {
    runContractCheck();
  } catch (error) {
    printResult({
      ok: false,
      mode,
      error: error instanceof Error ? error.message : String(error),
      browserStarted: false,
      previewStarted: false,
      networkUsed: false,
    });
    process.exitCode = 1;
  }
} else {
  await runBrowserQa();
}

async function runBrowserQa() {
const { chromium } = await import('playwright');

const host = '127.0.0.1';
const port = 4199;
const externalUrl = process.env.REHAB_GUI_URL;
const url = externalUrl || `http://${host}:${port}/`;
const viteCli = resolve('node_modules/vite/bin/vite.js');
const previewOutDir = process.env.PHASE19_QA_DIST;
const serverOutput = [];
const previewArgs = [viteCli, 'preview', '--host', host, '--port', String(port)];
if (previewOutDir) previewArgs.push('--outDir', previewOutDir);
const server = externalUrl
  ? null
  : spawn(process.execPath, previewArgs, {
      cwd: process.cwd(),
      stdio: ['ignore', 'pipe', 'pipe'],
    });
server?.stdout.on('data', (chunk) => serverOutput.push(String(chunk)));
server?.stderr.on('data', (chunk) => serverOutput.push(String(chunk)));

async function waitForServer(timeoutMs = 15_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // Bounded polling covers normal preview startup.
    }
    await new Promise((resolveDelay) => setTimeout(resolveDelay, 100));
  }
  throw new Error(`GUI did not respond within ${timeoutMs} ms.\n${serverOutput.join('')}`);
}

let browser;
try {
  await waitForServer();
  browser = await chromium.launch({ headless: true, timeout: 15_000 });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const pageErrors = [];
  page.on('pageerror', (error) => pageErrors.push(error.stack || String(error)));

  await page.addInitScript(() => {
    const frames = [];
    const frameRecords = [];
    const sockets = [];
    const nativeRequestAnimationFrame = window.requestAnimationFrame.bind(window);
    window.requestAnimationFrame = (callback) => nativeRequestAnimationFrame(callback);
    class FakeRosbridgeWebSocket {
      static CONNECTING = 0;
      static OPEN = 1;
      static CLOSING = 2;
      static CLOSED = 3;

      constructor(targetUrl) {
        this.url = targetUrl;
        this.readyState = FakeRosbridgeWebSocket.CONNECTING;
        this.onopen = null;
        this.onmessage = null;
        this.onerror = null;
        this.onclose = null;
        sockets.push(this);
        queueMicrotask(() => {
          this.readyState = FakeRosbridgeWebSocket.OPEN;
          this.onopen?.({ type: 'open' });
        });
      }

      send(payload) {
        const frame = JSON.parse(String(payload));
        frames.push(frame);
        frameRecords.push({ socketIndex: sockets.indexOf(this), frame });
      }

      close() {
        this.readyState = FakeRosbridgeWebSocket.CLOSED;
        this.onclose?.({ type: 'close' });
      }

      emit(envelope) {
        this.onmessage?.({ data: JSON.stringify(envelope) });
      }

      emitRaw(payload) {
        this.onmessage?.({ data: payload });
      }
    }

    window.WebSocket = FakeRosbridgeWebSocket;
    window.__phase19Rosbridge = {
      frames,
      sockets,
      frameRecords,
      serviceCalls() {
        return frames.filter((frame) => frame.op === 'call_service');
      },
      callsForSocket(socketIndex) {
        return frameRecords
          .filter((record) => (
            record.socketIndex === socketIndex
            && record.frame.op === 'call_service'
          ))
          .map((record) => record.frame);
      },
      subscriptionsForSocket(socketIndex) {
        return frameRecords
          .filter((record) => (
            record.socketIndex === socketIndex
            && record.frame.op === 'subscribe'
          ))
          .map((record) => record.frame);
      },
      respond(callIndex, success, message, socketIndex = sockets.length - 1) {
        const call = this.serviceCalls()[callIndex];
        if (!call) throw new Error(`Missing service call ${callIndex}`);
        sockets[socketIndex]?.emit({
          op: 'service_response',
          id: call.id,
          values: { success, message },
        });
      },
      respondCall(call, success, message, socketIndex = sockets.length - 1) {
        if (!call) throw new Error(`Missing service call on socket ${socketIndex}`);
        sockets[socketIndex]?.emit({
          op: 'service_response',
          id: call.id,
          values: { success, message },
        });
      },
      publishOpenSimStatus(
        visualization,
        calibration = {
          state: 'UNCALIBRATED',
          reason: '',
          calibration_id: null,
        },
        socketIndex = sockets.length - 1,
      ) {
        sockets[socketIndex]?.emit({
          op: 'publish',
          topic: '/opensim/status',
          msg: {
            data: JSON.stringify({
              schema: 'rehab.opensim_status.1',
              calibration,
              visualization,
            }),
          },
        });
      },
      publishIkStatus(
        solutionValid,
        reason,
        calibrationId,
        socketIndex = sockets.length - 1,
      ) {
        sockets[socketIndex]?.emit({
          op: 'publish',
          topic: '/opensim/ik_status',
          msg: {
            data: JSON.stringify({
              schema: 'rehab.opensim_ik_status.1',
              solution_valid: solutionValid,
              reason,
              calibration_id: calibrationId,
              input_age_s: 0.01,
            }),
          },
        });
      },
      publishJointState(
        names,
        positions,
        sec,
        nanosec = 0,
        socketIndex = sockets.length - 1,
      ) {
        sockets[socketIndex]?.emit({
          op: 'publish',
          topic: '/opensim/joint_states',
          msg: {
            header: { stamp: { sec, nanosec } },
            name: names,
            position: positions,
          },
        });
      },
      publishEspPair(timeUs, socketIndex = sockets.length - 1) {
        const sensorConfig = {
          accel_range_g: 8,
          gyro_range_dps: 2000,
          accel_lsb_per_g: 4096,
          gyro_lsb_per_dps: 16.384,
          units: {
            raw: 'count',
            accel_range: 'g',
            gyro_range: 'deg/s',
            accel_sensitivity: 'count/g',
            gyro_sensitivity: 'count/(deg/s)',
            linear_acceleration: 'm/s^2',
            angular_velocity: 'rad/s',
          },
        };
        for (const role of ['master', 'slave']) {
          sockets[socketIndex]?.emit({
            op: 'publish',
            topic: `/esp/raw/${role}`,
            msg: {
              data: JSON.stringify({
                topic_schema: 'oe_esp32.raw.v1',
                time_us: timeUs,
                role,
                sensor_config: sensorConfig,
                imu: { ax: 0, ay: 0, az: 4096, gx: 0, gy: 0, gz: 0 },
                quat: { qw: 32767, qx: 0, qy: 0, qz: 0 },
              }),
            },
          });
        }
      },
      emitRaw(payload, socketIndex = sockets.length - 1) {
        sockets[socketIndex]?.emitRaw(payload);
      },
      closeAgain(socketIndex) {
        sockets[socketIndex]?.onclose?.({ type: 'late-close' });
      },
    };
  });

  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 15_000 });
  const completedScenarios = new Set();
  const markScenario = (name) => {
    assert(CONTRACT.scenarios.includes(name), `Unknown QA scenario: ${name}`);
    completedScenarios.add(name);
  };
  const assertTriggerCall = (call, service, label) => {
    assert(call, `${label} did not send a service call`);
    assert(
      call.service === service
        && call.type === CONTRACT.triggerType
        && JSON.stringify(call.args) === '{}',
      `Unexpected ${label} Trigger frame: ${JSON.stringify(call)}`,
    );
  };

  const toolbarLabels = (await page.locator('.toolbar > button').allTextContents())
    .map((label) => label.trim());
  const calibrateIndex = toolbarLabels.indexOf('Calibrate');
  assert(
    calibrateIndex >= 0,
    `Calibrate button is missing; labels=${JSON.stringify(toolbarLabels)}; pageErrors=${JSON.stringify(pageErrors)}`,
  );
  assert(
    JSON.stringify(toolbarLabels.slice(calibrateIndex, calibrateIndex + 4))
      === JSON.stringify(['Calibrate', 'Clear cal', 'Open visualizer', 'Save']),
    `Unexpected toolbar order: ${toolbarLabels.join(' | ')}`,
  );
  markScenario('toolbar-order');

  await page.getByRole('button', { name: /Run/ }).click();
  await page.waitForFunction(() => (
    window.__phase19Rosbridge.frames
      .filter((frame) => frame.op === 'subscribe').length >= 6
  ));
  const subscriptions = await page.evaluate(() => (
    window.__phase19Rosbridge.subscriptionsForSocket(0)
  ));
  for (const [topic, type] of Object.entries(CONTRACT.subscriptions)) {
    const matches = subscriptions.filter((subscription) => (
      subscription.topic === topic && subscription.type === type
    ));
    assert(
      matches.length === 1,
      `Expected one ${topic} ${type} subscription, received ${JSON.stringify(matches)}`,
    );
  }

  const visualizerButton = page.getByRole('button', { name: 'Open visualizer' });
  await visualizerButton.focus();
  await page.evaluate(() => {
    window.__phase19OriginalButton = document.activeElement;
  });
  await visualizerButton.click();
  const openingButton = page.getByRole('button', { name: 'Opening…' });
  await openingButton.waitFor({ state: 'visible' });
  assert(await openingButton.isDisabled(), 'Opening button must be disabled');
  assert(
    await openingButton.getAttribute('aria-busy') === 'true',
    'Opening button must expose aria-busy=true',
  );
  assert(
    await page.evaluate(() => (
      document.querySelector('button[aria-busy="true"]') === window.__phase19OriginalButton
    )),
    'Busy label must retain the same button element',
  );

  await openingButton.dispatchEvent('click');
  await page.keyboard.press('Enter');
  await page.keyboard.press('Space');
  await page.waitForTimeout(100);
  const firstCalls = await page.evaluate(() => window.__phase19Rosbridge.serviceCalls());
  assert(firstCalls.length === 1, `Expected one service frame, received ${firstCalls.length}`);
  const visualizerCall = firstCalls[0];
  assertTriggerCall(visualizerCall, CONTRACT.visualizerService, 'visualizer');
  markScenario('visualizer-pending-duplicate-suppression');

  await page.evaluate(() => {
    window.__phase19Rosbridge.respond(0, false, 'simbody_visualizer_missing');
  });
  const alert = page.getByRole('alert');
  await alert.waitFor({ state: 'visible' });
  assert(
    await alert.textContent()
      === 'OpenSim visualizer could not open: Simbody visualizer missing. Check the OpenSim runtime, then retry.',
    `Unexpected failure alert: ${await alert.textContent()}`,
  );
  const retryButton = page.getByRole('button', { name: 'Open visualizer' });
  assert(!await retryButton.isDisabled(), 'Failure must restore retry');
  assert(await retryButton.getAttribute('aria-busy') === null, 'Settled button must clear aria-busy');
  assert(
    await page.evaluate(() => (
      [...document.querySelectorAll('button')]
        .find((button) => button.textContent?.trim() === 'Open visualizer')
      === window.__phase19OriginalButton
    )),
    'Failure settlement must retain the same button element',
  );

  await page.getByRole('button', { name: 'Front Panel' }).click();
  const visualizerHealth = page.getByText('3D visualizer', { exact: true })
    .locator('xpath=following-sibling::strong[1]');
  await visualizerHealth.waitFor({ state: 'visible' });
  assert(
    await visualizerHealth.textContent() === 'Failed — Simbody visualizer missing',
    `Failure did not persist in HealthPanel: ${await visualizerHealth.textContent()}`,
  );
  const failureLogs = page.locator('.log-row.level-error').filter({
    hasText: 'OpenSim visualizer failed - Simbody visualizer missing',
  });
  assert(
    await failureLogs.count() === 1,
    `Expected one visualizer ERROR log, received ${await failureLogs.count()}`,
  );

  await retryButton.click();
  await page.getByRole('button', { name: 'Opening…' }).waitFor({ state: 'visible' });
  assert(
    await visualizerHealth.textContent() === 'Opening…',
    'Retry pending state must be visible in HealthPanel',
  );
  const retryCalls = await page.evaluate(() => window.__phase19Rosbridge.serviceCalls());
  assert(retryCalls.length === 2, `Retry must send one new request, received ${retryCalls.length}`);

  await page.evaluate(() => {
    window.__phase19Rosbridge.respond(1, true, 'visualizer_request_accepted');
    window.__phase19Rosbridge.publishOpenSimStatus({
      available: true,
      state: 'opening',
      reason: '',
      model_path: '/models/gait2392.osim',
    });
  });
  await page.getByRole('button', { name: 'Open visualizer' }).waitFor({ state: 'visible' });
  assert(
    await visualizerHealth.textContent() === 'Opening…',
    'Backend Opening must replace the retained failure',
  );

  await page.evaluate(() => {
    window.__phase19Rosbridge.publishOpenSimStatus({
      available: true,
      state: 'open',
      reason: '',
      model_path: '/models/gait2392.osim',
    });
  });
  await visualizerHealth.getByText('Open', { exact: true }).waitFor({ state: 'visible' });
  assert(
    await page.evaluate(() => (
      [...document.querySelectorAll('button')]
        .find((button) => button.textContent?.trim() === 'Open visualizer')
      === window.__phase19OriginalButton
    )),
    'Backend recovery must retain the same toolbar button element',
  );

  markScenario('visualizer-failure-persistence-retry-success');

  if (mode === 'toolbar-only') {
    printResult({
      ok: true,
      mode,
      toolbarOrder: toolbarLabels.slice(calibrateIndex, calibrateIndex + 4),
      visualizerServiceCalls: retryCalls.length,
      persistentFailure: 'Failed — Simbody visualizer missing',
      recoveredState: 'Open',
      completedScenarios: [...completedScenarios],
    });
    return;
  }

  const motorPanel = page.locator('.dash-panel').filter({ hasText: 'Motor / Joint' });
  const motorKnee = motorPanel.locator('.knee-angle-value');
  const healthKnee = page.getByText('OpenSim knee angle', { exact: true })
    .locator('xpath=following-sibling::strong[1]');
  const calibrationButton = page.getByRole('button', { name: 'Calibrate' });

  await calibrationButton.click();
  await page.waitForFunction(() => window.__phase19Rosbridge.serviceCalls().length === 3);
  const calibrationCall = (await page.evaluate(() => (
    window.__phase19Rosbridge.serviceCalls()
  )))[2];
  assertTriggerCall(calibrationCall, CONTRACT.calibrationService, 'calibration');
  await page.evaluate(() => {
    window.__phase19Rosbridge.publishOpenSimStatus(
      { available: true, state: 'open', reason: '', model_path: '/models/gait2392.osim' },
      { state: 'CAPTURING', reason: '', calibration_id: null },
    );
    window.__phase19Rosbridge.respond(2, true, 'capturing');
  });
  await page.getByRole('button', { name: 'Calibrate' }).waitFor({ state: 'visible' });
  markScenario('standing-calibration');

  await page.evaluate(() => {
    window.__phase19Rosbridge.publishOpenSimStatus(
      { available: true, state: 'open', reason: '', model_path: '/models/gait2392.osim' },
      { state: 'CALIBRATED', reason: '', calibration_id: 'cal-e2e' },
    );
    window.__phase19Rosbridge.publishIkStatus(
      false,
      'orientation_solver_waiting',
      'cal-e2e',
    );
  });
  await page.waitForFunction(() => (
    document.querySelector('.dash-panel .knee-angle-value')?.textContent === '—'
  ));
  assert(await motorKnee.textContent() === '—', 'Invalid IK must render an em dash');
  assert(
    await motorPanel.getByText('Waiting for calibrated IK', { exact: true }).count() === 1,
    'Invalid IK must retain the waiting copy',
  );
  markScenario('invalid-em-dash');

  await page.evaluate(() => {
    window.__phase19Rosbridge.publishIkStatus(true, '', 'cal-e2e');
    window.__phase19Rosbridge.publishJointState(
      ['hip_flexion_r', 'knee_angle_r', 'ankle_angle_r'],
      [0.25, Math.PI / 2, -0.1],
      20,
      1,
    );
    window.__phase19Rosbridge.publishEspPair(2_000_000);
  });
  await motorKnee.getByText('90.0 deg', { exact: true }).waitFor({ state: 'visible' });
  assert(
    await healthKnee.textContent() === '90.0 deg',
    `HealthPanel did not render 90.0 deg: ${await healthKnee.textContent()}`,
  );
  await page.getByRole('button', { name: 'Block Diagram' }).click();
  const jointDisplayBlock = page.locator('.block-node').filter({ hasText: 'Joint Angle Display' });
  const diagramKnee = jointDisplayBlock.locator('.knee-angle-value');
  await diagramKnee.getByText('90.0 deg', { exact: true }).waitFor({ state: 'visible' });
  markScenario('reordered-pi-over-two-all-displays');

  await page.waitForTimeout(2_001);
  await diagramKnee.getByText('—', { exact: true }).waitFor({ state: 'visible' });
  await page.getByRole('button', { name: 'Front Panel' }).click();
  await motorKnee.getByText('—', { exact: true }).waitFor({ state: 'visible' });
  assert(
    await healthKnee.textContent() === 'Stale',
    `HealthPanel did not report stale JointState: ${await healthKnee.textContent()}`,
  );
  markScenario('stale-at-2001-ms');

  await page.evaluate(() => {
    window.__phase19Rosbridge.publishJointState(
      ['ankle_angle_r', 'knee_angle_r', 'hip_flexion_r'],
      [-0.1, Math.PI / 3, 0.25],
      21,
      0,
    );
    window.__phase19Rosbridge.publishEspPair(2_100_000);
  });
  await motorKnee.getByText('60.0 deg', { exact: true }).waitFor({ state: 'visible' });
  assert(
    await healthKnee.textContent() === '60.0 deg',
    `Recovery did not start with 60.0 deg: ${await healthKnee.textContent()}`,
  );
  markScenario('new-series-recovery');

  await page.evaluate(() => {
    window.__phase19Rosbridge.emitRaw('{not-json');
    window.__phase19Rosbridge.emitRaw(JSON.stringify({
      op: 'publish',
      topic: '/opensim/status',
      msg: { data: '{"calibration":{"state":"SPOOFED"}}' },
    }));
    window.__phase19Rosbridge.emitRaw(JSON.stringify({
      op: 'publish',
      topic: '/opensim/joint_states',
      msg: {
        header: { stamp: { sec: 22, nanosec: 1_000_000_000 } },
        name: ['knee_angle_r'],
        position: [999],
      },
    }));
    window.__phase19Rosbridge.emitRaw(JSON.stringify({
      op: 'service_response',
      id: { injected: true },
      values: { success: true, message: { raw: true } },
    }));
  });
  await page.waitForTimeout(100);
  assert(await motorKnee.textContent() === '60.0 deg', 'Malformed input mutated the live angle');
  assert(pageErrors.length === 0, `Malformed input raised page errors: ${JSON.stringify(pageErrors)}`);
  markScenario('malformed-envelope-isolation');

  await page.getByRole('button', { name: 'Open visualizer' }).click();
  await page.getByRole('button', { name: 'Opening…' }).waitFor({ state: 'visible' });
  const oldPendingCall = await page.evaluate(() => (
    window.__phase19Rosbridge.callsForSocket(0).at(-1)
  ));
  assertTriggerCall(oldPendingCall, CONTRACT.visualizerService, 'old-session visualizer');

  await page.getByRole('button', { name: /Stop/ }).click();
  await page.getByRole('button', { name: /Run/ }).click();
  await page.waitForFunction(() => (
    window.__phase19Rosbridge.subscriptionsForSocket(1).length >= 6
  ));
  const currentSubscriptions = await page.evaluate(() => (
    window.__phase19Rosbridge.subscriptionsForSocket(1)
  ));
  for (const [topic, type] of Object.entries(CONTRACT.subscriptions)) {
    assert(
      currentSubscriptions.filter((subscription) => (
        subscription.topic === topic && subscription.type === type
      )).length === 1,
      `Reconnect did not issue exactly one current ${topic} subscription`,
    );
  }
  await page.evaluate(() => {
    window.__phase19Rosbridge.publishOpenSimStatus(
      { available: true, state: 'open', reason: '', model_path: '/models/gait2392.osim' },
      { state: 'CALIBRATED', reason: '', calibration_id: 'cal-current' },
      1,
    );
    window.__phase19Rosbridge.publishIkStatus(true, '', 'cal-current', 1);
    window.__phase19Rosbridge.publishJointState(
      ['knee_angle_r'],
      [Math.PI / 4],
      30,
      0,
      1,
    );
    window.__phase19Rosbridge.publishEspPair(3_000_000, 1);
  });
  await motorKnee.getByText('45.0 deg', { exact: true }).waitFor({ state: 'visible' });

  await page.getByRole('button', { name: 'Open visualizer' }).click();
  await page.getByRole('button', { name: 'Opening…' }).waitFor({ state: 'visible' });
  const currentPendingCall = await page.evaluate(() => (
    window.__phase19Rosbridge.callsForSocket(1).at(-1)
  ));
  assertTriggerCall(currentPendingCall, CONTRACT.visualizerService, 'current-session visualizer');

  await page.evaluate(({ oldPendingCall }) => {
    window.__phase19Rosbridge.respondCall(oldPendingCall, true, 'late_old_success', 0);
    window.__phase19Rosbridge.publishOpenSimStatus(
      {
        available: false,
        state: 'failed',
        reason: 'obsolete_session_spoof',
        model_path: '',
      },
      {
        state: 'UNCALIBRATED',
        reason: 'obsolete_session_spoof',
        calibration_id: null,
      },
      0,
    );
    window.__phase19Rosbridge.publishIkStatus(false, 'obsolete_session_spoof', '', 0);
    window.__phase19Rosbridge.publishJointState(
      ['knee_angle_r'],
      [Math.PI],
      99,
      0,
      0,
    );
    window.__phase19Rosbridge.closeAgain(0);
  }, { oldPendingCall });
  await page.waitForTimeout(100);
  assert(
    await page.getByRole('button', { name: 'Opening…' }).isDisabled(),
    'Old-session reply/close settled the current visualizer request',
  );
  assert(await motorKnee.textContent() === '45.0 deg', 'Old-session message mutated current angle');
  assert(
    await page.evaluate(() => window.__phase19Rosbridge.sockets[1].readyState === 1),
    'Old-session close cleared the current socket',
  );
  await page.evaluate(({ currentPendingCall }) => {
    window.__phase19Rosbridge.respondCall(
      currentPendingCall,
      true,
      'visualizer_request_accepted',
      1,
    );
  }, { currentPendingCall });
  await page.getByRole('button', { name: 'Open visualizer' }).waitFor({ state: 'visible' });
  markScenario('obsolete-session-reply-message-close-rejection');

  const missingScenarios = CONTRACT.scenarios.filter((scenario) => !completedScenarios.has(scenario));
  assert(
    missingScenarios.length === 0,
    `Full QA did not complete scenarios: ${missingScenarios.join(', ')}`,
  );

  console.log(JSON.stringify({
    ok: true,
    mode,
    toolbarOrder: toolbarLabels.slice(calibrateIndex, calibrateIndex + 4),
    visualizerServiceCalls: retryCalls.length,
    persistentFailure: 'Failed — Simbody visualizer missing',
    recoveredState: 'Open',
    liveAngleAllDisplays: '90.0 deg',
    staleBoundaryMs: 2_001,
    recoveredSeriesValue: '60.0 deg',
    malformedIsolation: true,
    obsoleteSessionIsolation: true,
    completedScenarios: [...completedScenarios],
  }, null, 2));
} catch (error) {
  printResult({
    ok: false,
    mode,
    error: error instanceof Error ? error.message : String(error),
  });
  process.exitCode = 1;
} finally {
  await browser?.close();
  server?.kill();
}
}
