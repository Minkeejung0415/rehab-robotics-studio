import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { chromium } from 'playwright';

const host = '127.0.0.1';
const port = 4201;
const url = `http://${host}:${port}/`;
const server = spawn(process.execPath, ['node_modules/vite/bin/vite.js', 'preview', '--host', host, '--port', String(port)], {
  stdio: ['ignore', 'pipe', 'pipe'],
});
const serverOutput = [];
server.stdout.on('data', (chunk) => serverOutput.push(String(chunk)));
server.stderr.on('data', (chunk) => serverOutput.push(String(chunk)));

async function waitForServer() {
  const deadline = Date.now() + 15_000;
  while (Date.now() < deadline) {
    try {
      if ((await fetch(url)).ok) return;
    } catch { /* preview is still starting */ }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`Preview did not start:\n${serverOutput.join('')}`);
}

let browser;
try {
  await waitForServer();
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.addInitScript(() => {
    const sockets = [];
    class FakeWebSocket {
      static CONNECTING = 0;
      static OPEN = 1;
      static CLOSING = 2;
      static CLOSED = 3;
      constructor() {
        this.readyState = FakeWebSocket.CONNECTING;
        sockets.push(this);
        queueMicrotask(() => {
          this.readyState = FakeWebSocket.OPEN;
          this.onopen?.({ type: 'open' });
        });
      }
      send(payload) { (this.frames ??= []).push(JSON.parse(String(payload))); }
      close() { this.readyState = FakeWebSocket.CLOSED; this.onclose?.({ type: 'close' }); }
    }
    window.WebSocket = FakeWebSocket;
    window.__frequencyTest = {
      calls: () => sockets.flatMap((socket) => socket.frames ?? []).filter((frame) => frame.op === 'call_service'),
      respond(call) {
        sockets.at(-1)?.onmessage?.({ data: JSON.stringify({
          op: 'service_response', id: call.id,
          values: { results: [{ successful: true, reason: '' }] },
        }) });
      },
      reject(call) {
        sockets.at(-1)?.onmessage?.({ data: JSON.stringify({
          op: 'service_response', id: call.id,
          values: { results: [{ successful: false, reason: 'rejected for regression test' }] },
        }) });
      },
    };
  });
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: 'Run' }).click();
  await page.getByRole('button', { name: 'Block Diagram' }).click();
  const rate = page.getByLabel('ESP32 pair sample rate');
  await rate.waitFor();

  await rate.fill('400');
  await rate.press('Enter');
  await page.waitForFunction(() => window.__frequencyTest.calls().length === 1);
  const first = await page.evaluate(() => window.__frequencyTest.calls()[0]);
  assert.equal(first.service, '/esp_bridge_master/set_parameters');
  assert.deepEqual(first.args, { parameters: [{ name: 'sample_rate_hz', value: { type: 2, integer_value: 400 } }] });
  await page.evaluate((call) => window.__frequencyTest.respond(call), first);
  await page.waitForFunction(() => document.querySelector('[aria-label="ESP32 pair sample rate"]')?.value === '400');
  assert.equal(await page.getByLabel('ESP32 effective sample rate').inputValue(), '400');

  await rate.fill('500');
  await rate.press('Enter');
  await page.waitForFunction(() => window.__frequencyTest.calls().length === 2);
  const second = await page.evaluate(() => window.__frequencyTest.calls()[1]);
  await page.evaluate((call) => window.__frequencyTest.reject(call), second);
  await page.waitForFunction(() => document.querySelector('[aria-label="ESP32 pair sample rate"]')?.value === '400');
  assert.equal(await page.getByLabel('ESP32 effective sample rate').inputValue(), '400');
  console.log('Frequency panel regression passed: 400 Hz is sent to hardware and only acknowledged values update the diagram.');
} finally {
  await browser?.close();
  server.kill();
}
