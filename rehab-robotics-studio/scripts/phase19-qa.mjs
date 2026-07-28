import { spawn } from 'node:child_process';
import { resolve } from 'node:path';
import { chromium } from 'playwright';

if (!process.argv.includes('--toolbar-only')) {
  throw new Error('phase19-qa.mjs currently requires --toolbar-only');
}

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

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

let browser;
try {
  await waitForServer();
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const pageErrors = [];
  page.on('pageerror', (error) => pageErrors.push(error.stack || String(error)));

  await page.addInitScript(() => {
    const frames = [];
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
        frames.push(JSON.parse(String(payload)));
      }

      close() {
        this.readyState = FakeRosbridgeWebSocket.CLOSED;
        this.onclose?.({ type: 'close' });
      }

      emit(envelope) {
        this.onmessage?.({ data: JSON.stringify(envelope) });
      }
    }

    window.WebSocket = FakeRosbridgeWebSocket;
    window.__phase19Rosbridge = {
      frames,
      serviceCalls() {
        return frames.filter((frame) => frame.op === 'call_service');
      },
      respond(callIndex, success, message) {
        const call = this.serviceCalls()[callIndex];
        if (!call) throw new Error(`Missing service call ${callIndex}`);
        sockets.at(-1)?.emit({
          op: 'service_response',
          id: call.id,
          values: { success, message },
        });
      },
      publishOpenSimStatus(visualization) {
        sockets.at(-1)?.emit({
          op: 'publish',
          topic: '/opensim/status',
          msg: {
            data: JSON.stringify({
              schema: 'rehab.opensim_status.1',
              calibration: {
                state: 'UNCALIBRATED',
                reason: '',
                calibration_id: null,
              },
              visualization,
            }),
          },
        });
      },
    };
  });

  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 15_000 });

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

  await page.getByRole('button', { name: /Run/ }).click();
  await page.waitForFunction(() => (
    window.__phase19Rosbridge.frames
      .filter((frame) => frame.op === 'subscribe').length >= 6
  ));

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
      document.activeElement === window.__phase19OriginalButton
      && document.querySelector('button[aria-busy="true"]') === window.__phase19OriginalButton
    )),
    'Busy label must retain the same focused button element',
  );

  await openingButton.dispatchEvent('click');
  await page.keyboard.press('Enter');
  await page.keyboard.press('Space');
  await page.waitForTimeout(100);
  const firstCalls = await page.evaluate(() => window.__phase19Rosbridge.serviceCalls());
  assert(firstCalls.length === 1, `Expected one service frame, received ${firstCalls.length}`);
  assert(
    firstCalls[0].service === '/opensim/visualizer/open'
      && firstCalls[0].type === 'std_srvs/srv/Trigger',
    `Unexpected visualizer service frame: ${JSON.stringify(firstCalls[0])}`,
  );

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
    await page.evaluate(() => document.activeElement === window.__phase19OriginalButton),
    'Failure settlement must retain focus on the same button',
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
    await page.evaluate(() => document.activeElement === window.__phase19OriginalButton),
    'Backend recovery must not move toolbar focus',
  );

  console.log(JSON.stringify({
    ok: true,
    mode: 'toolbar-only',
    toolbarOrder: toolbarLabels.slice(calibrateIndex, calibrateIndex + 4),
    visualizerServiceCalls: retryCalls.length,
    persistentFailure: 'Failed — Simbody visualizer missing',
    recoveredState: 'Open',
  }, null, 2));
} finally {
  await browser?.close();
  server?.kill();
}
