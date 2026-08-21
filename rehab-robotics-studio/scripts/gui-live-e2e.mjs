import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const baseUrl = process.env.GUI_URL ?? 'http://127.0.0.1:5173';
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on('console', (message) => {
  if (message.type() === 'error') errors.push(message.text());
});
page.on('pageerror', (error) => errors.push(error.message));

try {
  await page.goto(baseUrl, { waitUntil: 'networkidle', timeout: 30_000 });
  await expectText('Rehab Robotics Studio');
  await page.locator('.btn-run').click();
  await expectText('RUNNING');

  await page.getByRole('button', { name: 'Sensor Mapping' }).click();
  await page.getByRole('table', { name: 'Device segment assignments' }).waitFor({ timeout: 20_000 });
  await expectText('Model hash');
  assert.equal(await page.getByText('NO MODEL', { exact: true }).count(), 0, 'model catalog did not reach GUI');
  assert.equal(await page.locator('table tbody tr').count(), 2, 'both ESP rows must be visible');
  await page.screenshot({ path: '../logs/gui-e2e-mapping-before.png', fullPage: true });

  const rows = page.locator('table tbody tr');
  await rows.nth(0).locator('select').selectOption('femur_r\u001ffemur_r_imu');
  await rows.nth(1).locator('select').selectOption('tibia_r\u001ftibia_r_imu');
  await page.getByLabel(/Save assignment for device/).nth(0).click();
  await page.getByLabel(/Save assignment for device/).nth(1).click();
  await page.waitForTimeout(500);
  const apply = page.getByLabel('Apply mapping to runtime');
  await expectEnabled(apply, 12_000);
  await apply.click();
  await page.waitForTimeout(1_500);
  await expectText('APPLIED');
  await page.screenshot({ path: '../logs/gui-e2e-mapping-applied.png', fullPage: true });

  await page.getByRole('button', { name: 'Front Panel' }).click();
  await expectText('LIVE DASHBOARD');
  await expectText('Signal Contract');
  await page.getByRole('button', { name: 'Show Raw Counts' }).first().click();
  await expectText('ax');
  await expectText('gx');
  await expectText('mx');
  assert.ok(await page.locator('svg').count() > 0, 'front-panel graph SVGs are missing');
  await page.screenshot({ path: '../logs/gui-e2e-front-panel.png', fullPage: true });

  const record = page.locator('button[title^="Start or stop SD recording"]');
  await record.click();
  await page.waitForTimeout(1200);
  await record.click();
  const stop = page.locator('.toolbar > button.btn:not(.btn-estop)').filter({ hasText: 'Stop' });
  await stop.click();
  await expectText('IDLE');

  await page.getByRole('button', { name: 'Block Diagram' }).click();
  await expectText('BLOCK PALETTE');
  assert.ok(await page.locator('canvas, svg').count() > 0, 'block diagram surface is missing');
  await page.screenshot({ path: '../logs/gui-e2e-block-diagram.png', fullPage: true });

  assert.deepEqual(errors, [], `browser errors:\n${errors.join('\n')}`);
  console.log('GUI live E2E passed: model, two ESP rows, mapping save/apply, raw values, graphs, runtime, recording toggle, and diagram.');
} finally {
  await browser.close();
}

async function expectText(text) {
  await page.getByText(text, { exact: false }).first().waitFor({ state: 'visible', timeout: 12_000 });
}

async function expectEnabled(locator, timeout) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    if (await locator.isEnabled()) return;
    await page.waitForTimeout(200);
  }
  assert.fail('expected control to become enabled');
}
