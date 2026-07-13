import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const BASE = 'http://127.0.0.1:4173/';
const ISSUES_MD = path.join(
  ROOT,
  '.planning/phases/05-tabbed-workspace-layout/05-PLAYWRIGHT-ISSUES.md'
);
const FAIL_SHOT = path.join(
  ROOT,
  '.planning/phases/05-tabbed-workspace-layout/qa-fail.png'
);

const results = [];

function record(id, req, name, pass, detail = '', expected = '', actual = '') {
  results.push({ id, req, name, status: pass ? 'PASS' : 'FAIL', detail, expected, actual });
  console.log(
    `${pass ? 'PASS' : 'FAIL'} | ${id}. [${req}] ${name}${detail ? ' — ' + detail : ''}`
  );
}

async function shot(page) {
  try {
    fs.mkdirSync(path.dirname(FAIL_SHOT), { recursive: true });
    await page.screenshot({ path: FAIL_SHOT, fullPage: true });
    console.log(`Screenshot: ${FAIL_SHOT}`);
  } catch (e) {
    console.log(`Screenshot failed: ${e.message}`);
  }
}

function writeIssuesMd(headless, passed, failed) {
  const ts = new Date().toISOString();
  const lines = [
    '# Phase 5 Playwright Issues Log',
    '',
    '**Policy:** Record failures; do not auto-fix until user reviews.',
    '',
    `**Run:** ${ts}`,
    `**Base URL:** ${BASE}`,
    `**Script:** scripts/phase5-qa.mjs`,
    `**Headless:** ${headless}`,
    `**Summary:** ${passed} PASS / ${failed} FAIL / ${results.length} total`,
    '',
    '| # | Req | Check | Result | Details | Expected | Actual |',
    '|---|-----|-------|--------|---------|----------|--------|',
  ];

  for (const r of results) {
    const detail = (r.detail || '').replace(/\|/g, '/');
    const expected = (r.expected || '').replace(/\|/g, '/');
    const actual = (r.actual || '').replace(/\|/g, '/');
    lines.push(
      `| ${r.id} | ${r.req} | ${r.name} | **${r.status}** | ${detail} | ${expected} | ${actual} |`
    );
  }

  lines.push('');
  if (failed === 0) {
    lines.push('## Failures');
    lines.push('');
    lines.push('_None — all checklist items passed._');
  } else {
    lines.push('## Failures (record only — no code fixes applied)');
    lines.push('');
    for (const r of results.filter((x) => x.status === 'FAIL')) {
      lines.push(`### ${r.id}. [${r.req}] ${r.name}`);
      lines.push('');
      lines.push(`- **Expected:** ${r.expected || '(see check)'}`);
      lines.push(`- **Actual:** ${r.actual || r.detail || '(see details)'}`);
      lines.push(`- **Details:** ${r.detail}`);
      lines.push('');
    }
  }

  fs.mkdirSync(path.dirname(ISSUES_MD), { recursive: true });
  fs.writeFileSync(ISSUES_MD, lines.join('\n') + '\n', 'utf8');
  console.log(`Wrote ${ISSUES_MD}`);
}

async function main() {
  let browser;
  let headless = false;
  try {
    browser = await chromium.launch({ headless: false });
  } catch (e) {
    console.log(`headed launch failed (${e.message}); using headless`);
    headless = true;
    browser = await chromium.launch({ headless: true });
  }

  const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
  let anyFail = false;

  try {
    await page.goto(BASE, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(400);

    // ---------- 1. Tab strip visible with 2 tabs (TAB-01) ----------
    try {
      const tabStrip = page.locator('.tab-strip');
      const stripVisible = await tabStrip.isVisible();
      const tabs = page.locator('.tab-strip .tab');
      const tabCount = await tabs.count();
      const tabTexts = (await tabs.allTextContents()).map((t) => t.trim());
      const hasBothTabs =
        tabTexts.some((t) => /Block Diagram/i.test(t)) &&
        tabTexts.some((t) => /Front Panel/i.test(t));
      const pass = stripVisible && tabCount === 2 && hasBothTabs;
      record(
        1,
        'TAB-01',
        'Tab strip visible with Block Diagram and Front Panel tabs',
        pass,
        `stripVisible=${stripVisible}, tabCount=${tabCount}, tabs=[${tabTexts.join(', ')}]`,
        '.tab-strip with 2 .tab children: "Block Diagram" and "Front Panel"',
        `tabCount=${tabCount}, tabs=[${tabTexts.join(', ')}]`
      );
      if (!pass) { anyFail = true; await shot(page); }
    } catch (e) {
      anyFail = true;
      record(1, 'TAB-01', 'Tab strip visible with Block Diagram and Front Panel tabs', false, e.message, '2 tabs', e.message);
      await shot(page);
    }

    // ---------- 2. Default active tab is Block Diagram (TAB-01, TAB-04) ----------
    try {
      const activeTabs = page.locator('.tab.is-active');
      const activeCount = await activeTabs.count();
      const activeText = activeCount > 0 ? ((await activeTabs.first().textContent()) || '').trim() : '';
      const pass = activeCount === 1 && /Block Diagram/i.test(activeText);
      record(
        2,
        'TAB-01',
        'Default active tab is "Block Diagram"',
        pass,
        `activeCount=${activeCount}, activeText="${activeText}"`,
        'Exactly 1 .tab.is-active; text = "Block Diagram"',
        `activeCount=${activeCount}, text="${activeText}"`
      );
      if (!pass) { anyFail = true; await shot(page); }
    } catch (e) {
      anyFail = true;
      record(2, 'TAB-01', 'Default active tab is "Block Diagram"', false, e.message, 'Block Diagram active', e.message);
      await shot(page);
    }

    // ---------- 3. Block Diagram tab shows graph workspace (TAB-02) ----------
    try {
      const libraryVisible = await page.locator('.library').isVisible();
      const canvasVisible = await page.locator('.graph-canvas').isVisible();
      const propertiesVisible = await page.locator('.properties').isVisible();
      const dashboardPresent = await page.locator('.dashboard').isVisible().catch(() => false);
      const pass = libraryVisible && canvasVisible && propertiesVisible && !dashboardPresent;
      record(
        3,
        'TAB-02',
        'Block Diagram tab shows Library + Canvas + Properties; no Dashboard',
        pass,
        `library=${libraryVisible}, canvas=${canvasVisible}, properties=${propertiesVisible}, dashboard=${dashboardPresent}`,
        '.library, .graph-canvas, .properties visible; .dashboard not visible',
        `library=${libraryVisible}, canvas=${canvasVisible}, props=${propertiesVisible}, dash=${dashboardPresent}`
      );
      if (!pass) { anyFail = true; await shot(page); }
    } catch (e) {
      anyFail = true;
      record(3, 'TAB-02', 'Block Diagram tab shows Library + Canvas + Properties; no Dashboard', false, e.message, 'graph workspace', e.message);
      await shot(page);
    }

    // ---------- 4. Click Front Panel tab → Dashboard visible (TAB-03) ----------
    try {
      await page.getByRole('button', { name: /Front Panel/i }).click();
      await page.waitForTimeout(200);
      const frontPanelWorkspace = page.locator('.workspace--front-panel');
      const fpVisible = await frontPanelWorkspace.isVisible();
      const dashVisible = await page.locator('.dashboard').isVisible();
      const dashPanels = await page.locator('.dash-panel').count();
      const pass = fpVisible && dashVisible && dashPanels > 0;
      record(
        4,
        'TAB-03',
        'Front Panel tab → .workspace--front-panel + .dashboard + .dash-panel visible',
        pass,
        `fpVisible=${fpVisible}, dashVisible=${dashVisible}, dashPanels=${dashPanels}`,
        '.workspace--front-panel visible; .dashboard visible; at least 1 .dash-panel',
        `fpVisible=${fpVisible}, dashVisible=${dashVisible}, dashPanels=${dashPanels}`
      );
      if (!pass) { anyFail = true; await shot(page); }
    } catch (e) {
      anyFail = true;
      record(4, 'TAB-03', 'Front Panel tab → .workspace--front-panel + .dashboard + .dash-panel visible', false, e.message, 'dashboard visible', e.message);
      await shot(page);
    }

    // ---------- 5. Front Panel hides graph workspace (TAB-03) ----------
    try {
      const canvasVisible = await page.locator('.graph-canvas').isVisible().catch(() => false);
      const libraryVisible = await page.locator('.library').isVisible().catch(() => false);
      const pass = !canvasVisible && !libraryVisible;
      record(
        5,
        'TAB-03',
        'Front Panel tab hides graph canvas and library',
        pass,
        `canvasVisible=${canvasVisible}, libraryVisible=${libraryVisible}`,
        '.graph-canvas and .library not visible in Front Panel tab',
        `canvas=${canvasVisible}, library=${libraryVisible}`
      );
      if (!pass) { anyFail = true; await shot(page); }
    } catch (e) {
      anyFail = true;
      record(5, 'TAB-03', 'Front Panel tab hides graph canvas and library', false, e.message, 'canvas hidden', e.message);
      await shot(page);
    }

    // ---------- 6. Front Panel tab is now active (TAB-04) ----------
    try {
      const activeText = ((await page.locator('.tab.is-active').first().textContent()) || '').trim();
      const pass = /Front Panel/i.test(activeText);
      record(
        6,
        'TAB-04',
        'Front Panel tab has is-active class when selected',
        pass,
        `activeText="${activeText}"`,
        '.tab.is-active text = "Front Panel"',
        `activeText="${activeText}"`
      );
      if (!pass) { anyFail = true; await shot(page); }
    } catch (e) {
      anyFail = true;
      record(6, 'TAB-04', 'Front Panel tab has is-active class when selected', false, e.message, 'is-active on Front Panel', e.message);
      await shot(page);
    }

    // ---------- 7. Click Block Diagram → back to graph workspace (TAB-02) ----------
    try {
      await page.getByRole('button', { name: /Block Diagram/i }).click();
      await page.waitForTimeout(200);
      const canvasVisible = await page.locator('.graph-canvas').isVisible();
      const dashboardVisible = await page.locator('.dashboard').isVisible().catch(() => false);
      const pass = canvasVisible && !dashboardVisible;
      record(
        7,
        'TAB-02',
        'Click Block Diagram → canvas visible; dashboard gone',
        pass,
        `canvasVisible=${canvasVisible}, dashboardVisible=${dashboardVisible}`,
        '.graph-canvas visible; .dashboard not visible',
        `canvas=${canvasVisible}, dashboard=${dashboardVisible}`
      );
      if (!pass) { anyFail = true; await shot(page); }
    } catch (e) {
      anyFail = true;
      record(7, 'TAB-02', 'Click Block Diagram → canvas visible; dashboard gone', false, e.message, 'canvas back', e.message);
      await shot(page);
    }

    // ---------- 8. Toolbar present in both tabs (regression) ----------
    try {
      const toolbarVisible = await page.locator('.toolbar').isVisible();
      // Switch to Front Panel and check
      await page.getByRole('button', { name: /Front Panel/i }).click();
      await page.waitForTimeout(150);
      const toolbarInFP = await page.locator('.toolbar').isVisible();
      await page.getByRole('button', { name: /Block Diagram/i }).click();
      await page.waitForTimeout(150);
      const pass = toolbarVisible && toolbarInFP;
      record(
        8,
        'REG',
        'Toolbar visible in both Block Diagram and Front Panel tabs',
        pass,
        `inDiagram=${toolbarVisible}, inFrontPanel=${toolbarInFP}`,
        '.toolbar visible in both tabs',
        `inDiagram=${toolbarVisible}, inFrontPanel=${toolbarInFP}`
      );
      if (!pass) { anyFail = true; await shot(page); }
    } catch (e) {
      anyFail = true;
      record(8, 'REG', 'Toolbar visible in both Block Diagram and Front Panel tabs', false, e.message, 'toolbar in both', e.message);
      await shot(page);
    }

    // ---------- 9. Status strip present in both tabs (regression) ----------
    try {
      const stripVisible = await page.locator('.status-strip').isVisible();
      await page.getByRole('button', { name: /Front Panel/i }).click();
      await page.waitForTimeout(150);
      const stripInFP = await page.locator('.status-strip').isVisible();
      await page.getByRole('button', { name: /Block Diagram/i }).click();
      await page.waitForTimeout(150);
      const pass = stripVisible && stripInFP;
      record(
        9,
        'REG',
        'Status strip visible in both Block Diagram and Front Panel tabs',
        pass,
        `inDiagram=${stripVisible}, inFrontPanel=${stripInFP}`,
        '.status-strip visible in both tabs',
        `inDiagram=${stripVisible}, inFrontPanel=${stripInFP}`
      );
      if (!pass) { anyFail = true; await shot(page); }
    } catch (e) {
      anyFail = true;
      record(9, 'REG', 'Status strip visible in both Block Diagram and Front Panel tabs', false, e.message, 'status-strip in both', e.message);
      await shot(page);
    }

    // ---------- 10. Phase 4 regression: Run → badges; Deploy toast (REG) ----------
    try {
      // Ensure on Block Diagram tab
      const activeText = ((await page.locator('.tab.is-active').first().textContent()) || '').trim();
      if (!/Block Diagram/i.test(activeText)) {
        await page.getByRole('button', { name: /Block Diagram/i }).click();
        await page.waitForTimeout(150);
      }
      await page.locator('.graph-canvas').waitFor({ state: 'visible', timeout: 5000 });
      const blockCount = await page.locator('.block-node').count();
      // Deploy toast regression
      await page.getByRole('button', { name: /Deploy Mock/i }).click();
      await page.waitForTimeout(200);
      const toasts = await page.locator('.toast').allTextContents();
      const toastOk = toasts.some((t) => /Deploy \(mock\) started/i.test(t));
      const pass = blockCount > 0 && toastOk;
      record(
        10,
        'REG',
        'Phase 4 regression: blocks on canvas + Deploy toast works',
        pass,
        `blockCount=${blockCount}, toastOk=${toastOk}, toasts=[${toasts.join(' | ')}]`,
        'Blocks present on canvas; Deploy Mock shows toast',
        `blocks=${blockCount}, toastOk=${toastOk}`
      );
      if (!pass) { anyFail = true; await shot(page); }
    } catch (e) {
      anyFail = true;
      record(10, 'REG', 'Phase 4 regression: blocks on canvas + Deploy toast works', false, e.message, 'blocks + toast', e.message);
      await shot(page);
    }
  } catch (e) {
    console.error('Fatal:', e);
    anyFail = true;
    try { await shot(page); } catch {}
    record('FATAL', '—', 'Suite setup / navigation', false, String(e.message || e), 'App loads', String(e.message || e));
  } finally {
    await browser.close();
  }

  const passed = results.filter((r) => r.status === 'PASS').length;
  const failed = results.filter((r) => r.status === 'FAIL').length;
  writeIssuesMd(headless, passed, failed);

  console.log('\n## Phase 5 Browser Checklist Results\n');
  console.log('| # | Req | Test | Status | Detail |');
  console.log('|---|-----|------|--------|--------|');
  for (const r of results) {
    console.log(`| ${r.id} | ${r.req} | ${r.name} | ${r.status} | ${(r.detail || '').replace(/\|/g, '/')} |`);
  }
  console.log(`\nSummary: ${passed} PASS / ${failed} FAIL / ${results.length} total`);
  console.log(JSON.stringify({ headless, passed, failed, results }, null, 2));

  process.exit(failed > 0 || anyFail ? 1 : 0);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
