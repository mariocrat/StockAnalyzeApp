// Focused F4 DOM evidence: original archive JSX, canonical renderer and real CSS.
// No build, app server, provider requests or chart-canvas assertions.
// Usage: node this-file EVIDENCE_ROOT EXISTING_PLAYWRIGHT_ROOT BROWSER_EXE
import assert from 'node:assert/strict';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ts from 'typescript';
import CanonicalReviewRenderer, { validateReviewDisplay } from '../src/components/CanonicalReviewRenderer.js';
import { aiReviewChartSource } from '../src/utils/aiReviewChartSource.js';

const [evidenceArg, playwrightRoot, executablePath] = process.argv.slice(2);
assert.ok(evidenceArg && playwrightRoot && executablePath, 'explicit existing runtime paths required');
const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const evidenceRoot = resolve(evidenceArg);
const handoff = JSON.parse(await readFile(join(evidenceRoot,
  'browser-fixtures/scripts/fixtures/generated-review-chart-results.json'), 'utf8'));
assert.equal(handoff.passed, true);
assert.equal(handoff.unexpected, 0);
assert.equal(handoff.restored, true);
assert.equal(handoff.patches_restored, true);
assert.equal(handoff.history_titles.length, 10);
const source = await readFile(join(frontend, 'src/components/TradingJournal.jsx'), 'utf8');
const css = await readFile(join(frontend, 'src/App.css'), 'utf8');
const ast = ts.createSourceFile('TradingJournal.jsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.JSX);
assert.deepEqual(ast.parseDiagnostics, []);
const journal = ast.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === 'TradingJournal');
const archive = journal.body.statements.filter(ts.isVariableStatement)
  .find(statement => statement.declarationList.declarations.some(node => node.name.getText(ast) === 'renderReviewHistoryArchive'));
assert.ok(archive);
const lowered = ts.transpileModule(archive.getText(ast), { fileName: 'production.jsx', reportDiagnostics: true,
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React } });
assert.deepEqual(lowered.diagnostics, []);

function productionHtml(record, listed, ticker) {
  const noop = () => {};
  const bindings = { React, CanonicalReviewRenderer, aiReviewChartSource,
    activeReviewHistory: record, reviewHistory: [listed], reviewHistoryLoading: false,
    activeChartTicker: ticker, authSession: { user: { journal_storage_enabled: true } },
    setActiveChartTicker: noop, loadReviewHistory: noop, openReviewHistoryDetail: noop,
    deleteReviewHistoryItem: noop, restoreReviewHistoryTrades: noop, dateTimeText: value => value,
    JournalTradeChart: () => null };
  const render = new Function(...Object.keys(bindings), `${lowered.outputText}\nreturn renderReviewHistoryArchive;`)
    (...Object.values(bindings));
  return renderToStaticMarkup(React.createElement('main', { className: 'journal-page' }, render()));
}

const artifactRoot = join(evidenceRoot, 'history-title-browser-evidence');
await mkdir(artifactRoot, { recursive: true });
const report = { scope: 'F4 original history JSX and canonical renderer in browser DOM with production CSS',
  viewports: [1280, 390], checks: [], requests: [], pageErrors: [], browserClosed: false };
const { chromium } = await import(pathToFileURL(join(playwrightRoot, 'index.mjs')).href);
let browser;

async function inspect(locator, document, surface) {
  assert.equal(validateReviewDisplay(document, surface), document.canonical_text);
  await locator.waitFor({ state: 'visible' });
  await locator.scrollIntoViewIfNeeded();
  const actual = await locator.evaluate(root => {
    const spans = Array.from(root.querySelectorAll('.canonical-review-display'));
    const canonical = spans[0];
    const range = document.createRange();
    range.selectNodeContents(root);
    const rects = Array.from(range.getClientRects());
    const hidden = [];
    for (let element = root; element; element = element.parentElement) {
      const style = getComputedStyle(element);
      if (style.display === 'none' || style.visibility !== 'visible' || Number(style.opacity) === 0) hidden.push(element.tagName);
    }
    return { text: root.textContent, visibleText: root.innerText,
      canonicalNodes: spans.length, whitespace: canonical && getComputedStyle(canonical).whiteSpace,
      visible: rects.length > 0, hidden, blocks: Array.from(root.querySelectorAll('[data-review-block]'))
        .map(block => ({ type: block.dataset.reviewBlock, text: block.textContent })) };
  });
  assert.equal(actual.text, document.canonical_text);
  assert.equal(actual.visibleText, document.canonical_text);
  assert.equal(actual.canonicalNodes, 1);
  assert.equal(actual.whitespace, 'pre-wrap');
  assert.equal(actual.visible, true);
  assert.deepEqual(actual.hidden, []);
  assert.deepEqual(actual.blocks, document.blocks.map(block => ({ type: block.type,
    text: block.runs.map(run => run.text).join('') })));
  return actual;
}

try {
  browser = await chromium.launch({ executablePath, headless: true,
    args: ['--disable-background-networking', '--disable-component-update', '--disable-sync', '--no-first-run'] });
  report.browserVersion = browser.version();
  for (const width of report.viewports) {
    const context = await browser.newContext({ viewport: { width, height: 960 },
      serviceWorkers: 'block', locale: 'ko-KR', timezoneId: 'Asia/Seoul' });
    await context.route('**/*', route => { report.requests.push(route.request().url()); return route.abort(); });
    const page = await context.newPage();
    page.on('pageerror', error => report.pageErrors.push(error.message));
    try {
      for (const [index, row] of handoff.history_titles.entries()) {
        let record = row.detail;
        if (row.case === 'new') {
          const snapshot = record.ai_review.chart_display_snapshot;
          const chart = snapshot.charts[0];
          // Layout-only second ticker: every document remains the backend's
          // original approved value, also checked against its sealed projection.
          assert.deepEqual(snapshot, row.snapshot);
          record = { ...record, ai_review: { ...record.ai_review, chart_display_snapshot: {
            ...snapshot, charts: [chart, { ...chart, ticker: '000660' }],
          } } };
        }
        const charts = aiReviewChartSource(record.ai_review, record).charts;
        for (const ticker of charts.length ? charts.map(chart => chart.ticker) : ['']) {
          const check = { width, case: row.case, fixture: index, ticker, passed: false };
          report.checks.push(check);
          await page.setContent(`<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>${css}</style></head><body>${productionHtml(record, row.listed, ticker)}</body></html>`);
          check.list = await inspect(page.locator('.review-history-list button:not(.journal-secondary) > strong'), row.listed.display_snapshot, 'body');
          check.detail = await inspect(page.locator('.review-history-detail h4'), row.detail.display_snapshot, 'body');
          assert.equal(check.list.text, check.detail.text);
          assert.equal(check.list.visibleText, check.detail.visibleText);
          const buttons = page.locator('.journal-chart-tabs button');
          assert.equal(await buttons.count(), charts.length > 1 ? charts.length : 0);
          check.tabs = [];
          for (const [chartIndex, chart] of charts.entries()) {
            if (charts.length > 1) check.tabs.push(await inspect(buttons.nth(chartIndex),
              chart.tab || chart.display_snapshot, chart.tab ? 'chart_tab' : 'body'));
          }
          check.passed = true;
        }
      }
      await page.screenshot({ path: join(artifactRoot, `history-${width}.png`), fullPage: true });
    } finally { await context.close(); }
  }
  assert.deepEqual(report.requests, []);
  assert.deepEqual(report.pageErrors, []);
} finally {
  if (browser) { await browser.close(); report.browserClosed = true; }
  report.passed = report.checks.length === 38 && report.checks.every(check => check.passed)
    && report.requests.length === 0 && report.pageErrors.length === 0 && report.browserClosed;
  await writeFile(join(artifactRoot, 'browser-report.json'), JSON.stringify(report, null, 2));
}
assert.equal(report.passed, true);
console.log(JSON.stringify({ passed: report.passed, checks: report.checks.length,
  viewports: report.viewports, externalRequests: report.requests.length, pageErrors: report.pageErrors.length,
  browserClosed: report.browserClosed, artifactRoot }));
