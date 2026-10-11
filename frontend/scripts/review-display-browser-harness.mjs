// Supplemental Phase 5 browser evidence. No production module is replaced.
// Usage: node this-file EVIDENCE_ROOT EXISTING_PLAYWRIGHT_ROOT BROWSER_EXE [--client-gate-only|--marker-tooltip-only]
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { dirname, extname, join, resolve, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { validateReviewDisplay } from '../src/components/CanonicalReviewRenderer.js';

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const [evidenceRootArg, playwrightRoot, executablePath, mode] = process.argv.slice(2);
assert.ok(evidenceRootArg && playwrightRoot && executablePath, 'explicit existing runtime paths required');
assert.ok(mode === undefined || mode === '--client-gate-only' || mode === '--marker-tooltip-only', 'unknown browser selection');
const gateOnly = mode === '--client-gate-only';
const tooltipOnly = mode === '--marker-tooltip-only';
const evidenceRoot = resolve(evidenceRootArg);
const handoff = JSON.parse(await readFile(join(evidenceRoot,
  'browser-fixtures/scripts/fixtures/generated-review-chart-results.json'), 'utf8'));
assert.equal(handoff.passed, true);
assert.equal(handoff.unexpected, 0);
const vectors = JSON.parse(await readFile(join(frontend, 'scripts/fixtures/review-display-v1.json'), 'utf8'));
const { chromium } = await import(pathToFileURL(join(playwrightRoot, 'index.mjs')).href);
const artifactRoot = join(evidenceRoot, 'browser-evidence');
await mkdir(artifactRoot, { recursive: true });
const report = { scope: gateOnly ? 'client gate notice only' : tooltipOnly ? 'marker tooltip CSS only' : 'full Phase 5 browser matrix',
  checks: [], requests: [], externalRequests: [], pageErrors: [], findings: [],
  browserClosed: false, serverClosed: false };
const dist = join(frontend, 'dist');
const mime = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css',
  '.png': 'image/png', '.svg': 'image/svg+xml', '.mjs': 'text/javascript', '.wasm': 'application/wasm' };
const server = createServer(async (request, response) => {
  try {
    const pathname = decodeURIComponent(new URL(request.url, 'http://127.0.0.1').pathname);
    const path = resolve(dist, '.' + (pathname === '/' ? '/index.html' : pathname));
    if (!path.startsWith(dist + sep)) throw new Error('outside static build');
    response.writeHead(200, { 'content-type': mime[extname(path)] || 'application/octet-stream' });
    response.end(await readFile(path));
  } catch {
    response.writeHead(404);
    response.end();
  }
});
await new Promise(done => server.listen(0, '127.0.0.1', done));
const origin = `http://127.0.0.1:${server.address().port}`;
let browser;
let activePage;

function bodyExpectations(document) {
  let offset = 0;
  const strong = [];
  for (const block of document.blocks) {
    for (const run of block.runs) {
      const end = offset + Array.from(run.text).length;
      if (run.type === 'strong') strong.push({ start: offset, end, text: run.text });
      offset = end;
    }
    offset += Array.from(block.separator_after).length;
  }
  return { text: document.canonical_text, strong,
    blocks: document.blocks.map(block => ({ type: block.type, text: block.runs.map(run => run.text).join('') })) };
}

async function inspectDom(locator, document, label, width) {
  await locator.waitFor({ state: 'visible' });
  await locator.scrollIntoViewIfNeeded();
  const actual = await locator.evaluate(root => {
    const strong = [];
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let offset = 0;
    const clipping = [];
    while (walker.nextNode()) {
      const node = walker.currentNode;
      const start = offset;
      offset += Array.from(node.data).length;
      if (node.parentElement.closest('strong')) strong.push({ start, end: offset, text: node.data });
      if (!node.data.trim()) continue;
      const range = document.createRange();
      range.selectNodeContents(node);
      const rects = Array.from(range.getClientRects());
      if (!rects.length) clipping.push({ kind: 'no text rectangles', text: node.data });
      for (let parent = node.parentElement; parent; parent = parent.parentElement) {
        const style = getComputedStyle(parent);
        if (style.display === 'none' || style.visibility !== 'visible' || Number(style.opacity) === 0
            || parseFloat(style.fontSize) === 0 || style.contentVisibility === 'hidden') {
          clipping.push({ kind: 'hidden ancestor', tag: parent.tagName, className: parent.className });
        }
        const bounds = parent.getBoundingClientRect();
        if (['hidden', 'clip'].includes(style.overflowX) && rects.some(rect =>
          rect.left < bounds.left - 1 || rect.right > bounds.right + 1)) {
          clipping.push({ kind: 'horizontal clipping', className: parent.className });
        }
        if (['hidden', 'clip'].includes(style.overflowY) && rects.some(rect =>
          rect.top < bounds.top - 1 || rect.bottom > bounds.bottom + 1)) {
          clipping.push({ kind: 'vertical clipping', className: parent.className });
        }
        if (style.webkitLineClamp !== 'none' && style.webkitLineClamp !== '0'
            && parent.scrollHeight > parent.clientHeight + 1) {
          clipping.push({ kind: 'line clamp', className: parent.className });
        }
      }
    }
    return { text: root.textContent, visibleText: root.innerText, strong,
      blocks: Array.from(root.querySelectorAll('[data-review-block]')).map(block =>
        ({ type: block.dataset.reviewBlock, text: block.textContent, display: getComputedStyle(block).display })),
      whiteSpace: getComputedStyle(root).whiteSpace, clipping,
      width: root.getBoundingClientRect().width, height: root.getBoundingClientRect().height };
  });
  const expected = bodyExpectations(document);
  const problems = [];
  if (actual.text !== expected.text) problems.push('DOM logical text mismatch');
  if (actual.visibleText !== expected.text) problems.push('browser visible text mismatch');
  if (JSON.stringify(actual.strong) !== JSON.stringify(expected.strong)) problems.push('strong range mismatch');
  if (JSON.stringify(actual.blocks.map(({ type, text }) => ({ type, text }))) !== JSON.stringify(expected.blocks)) {
    problems.push('paragraph/block sequence mismatch');
  }
  if (actual.whiteSpace !== 'pre-wrap') problems.push('canonical whitespace not pre-wrap');
  if (actual.clipping.length) problems.push('CSS text clipping/visibility');
  const check = { label, viewportWidth: width, expected, actual, problems, passed: !problems.length };
  report.checks.push(check);
  if (problems.length) {
    report.findings.push(check);
    await locator.screenshot({ path: join(artifactRoot, 'production-finding.png') });
    throw new Error(`PRODUCTION_FINDING ${label}: ${problems.join(', ')}`);
  }
  return check;
}

const ready = handoff.results[0];
const strongTooltip = structuredClone(ready);
const strongTooltipDocument = structuredClone(vectors.valid.find(vector => vector.id === 'normal_bold').document);
strongTooltipDocument.surface = 'marker_tooltip';
validateReviewDisplay(strongTooltipDocument, 'marker_tooltip');
strongTooltip.snapshot.charts[0].markers[0].tooltip = strongTooltipDocument;
strongTooltip.response.chart_display_snapshot.charts[0].markers[0].tooltip = strongTooltipDocument;

// Execute the original production legacy DOM branch with real browser DOM and CSS.
// This compatibility fixture is separate from approved canonical review content.
const chartSource = await readFile(join(frontend, 'src/components/JournalTradeChart.jsx'), 'utf8');
const legacyStart = chartSource.indexOf('tooltip.replaceChildren();');
const legacyEnd = chartSource.lastIndexOf('}', chartSource.indexOf("tooltip.style.display = 'block';", legacyStart));
const legacyFormatter = chartSource.match(/^const intFmt = .*;$/m)?.[0];
assert.ok(legacyStart > 0 && legacyEnd > legacyStart && legacyFormatter);
const legacyProgram = `${legacyFormatter}\n${chartSource.slice(legacyStart, legacyEnd)}`;
const legacyMarkers = [
  { side: 'buy', tooltip: { label: '매수', count: 2, avg_price: 70200, total_quantity: 2, prices: [70000, 70400] } },
  { side: 'sell', tooltip: { label: '매도', count: 1, avg_price: 70900, total_quantity: 1, prices: [70900], profit_amount: 700, return_rate: 1 } },
];

async function inspectLegacyTooltip(page, width) {
  const actual = await page.locator('.journal-trade-chart').evaluate((container, { program, markers }) => {
    const tooltip = document.createElement('div');
    tooltip.className = 'journal-marker-tooltip';
    tooltip.style.left = '8px';
    tooltip.style.top = '8px';
    container.appendChild(tooltip);
    try {
      new Function('tooltip', 'matchedMarkers', program)(tooltip, markers);
      return Array.from(tooltip.children).map(section => Array.from(section.children).map(node => {
        const style = getComputedStyle(node);
        const range = document.createRange();
        range.selectNodeContents(node);
        const rects = Array.from(range.getClientRects());
        const clipping = [];
        for (let parent = node; parent; parent = parent.parentElement) {
          const parentStyle = getComputedStyle(parent);
          const bounds = parent.getBoundingClientRect();
          if (parentStyle.display === 'none' || parentStyle.visibility !== 'visible' || Number(parentStyle.opacity) === 0) clipping.push('hidden');
          if (['hidden', 'clip'].includes(parentStyle.overflowX) && rects.some(rect => rect.left < bounds.left - 1 || rect.right > bounds.right + 1)) clipping.push('horizontal');
          if (['hidden', 'clip'].includes(parentStyle.overflowY) && rects.some(rect => rect.top < bounds.top - 1 || rect.bottom > bounds.bottom + 1)) clipping.push('vertical');
        }
        return { tag: node.tagName.toLowerCase(), text: node.textContent, visibleText: node.innerText,
          display: style.display, color: style.color, fontSize: style.fontSize, fontStyle: style.fontStyle,
          marginTop: style.marginTop, top: node.getBoundingClientRect().top,
          visible: rects.length > 0, clipping };
      }));
    } finally { tooltip.remove(); }
  }, { program: legacyProgram, markers: legacyMarkers });
  const expected = [
    [['strong', '매수 2건'], ['span', '평균 70,200원 · 수량 2'], ['em', '70,000, 70,400원']],
    [['strong', '매도'], ['span', '평균 70,900원 · 수량 1'], ['em', '70,900원'], ['b', '실현 +700원 · +1%']],
  ];
  const problems = [];
  if (JSON.stringify(actual.map(section => section.map(node => [node.tag, node.text]))) !== JSON.stringify(expected)) problems.push('legacy content/order');
  for (const section of actual) for (const [index, node] of section.entries()) {
    if (node.display !== 'block' || !node.visible || node.visibleText !== node.text || node.clipping.length) problems.push('legacy layout/visibility');
    if (index && node.top <= section[index - 1].top) problems.push('legacy vertical order');
    if (node.tag === 'em' && node.fontStyle !== 'normal') problems.push('legacy price style');
  }
  if (actual[0][0].color !== 'rgb(95, 147, 255)' || actual[1][0].color !== 'rgb(255, 100, 112)') problems.push('legacy side colors');
  const check = { label: 'legacy-tooltip', viewportWidth: width, expected, actual, problems, passed: !problems.length };
  report.checks.push(check);
  if (problems.length) {
    report.findings.push(check);
    throw new Error(`PRODUCTION_FINDING legacy-tooltip: ${problems.join(', ')}`);
  }
}
const strong = handoff.body_results.find(row => row.review_type === 'basic' && row.body_case === 'strong');
const whitespace = structuredClone(ready);
whitespace.response.display_snapshot = vectors.valid.find(vector => vector.id === 'whitespace_and_newline').document;
const snapshotless = structuredClone(ready);
delete snapshotless.response.display_snapshot;
snapshotless.response.summary = 'RAW_SUMMARY_FALLBACK_FORBIDDEN';
snapshotless.response.structured_review = { main_issue: 'RAW_STRUCTURED_FALLBACK_FORBIDDEN' };
const scenarios = [
  ['live-basic', ready], ['live-advanced', handoff.results[1]], ['live-strong', strong],
  ['live-whitespace', whitespace],
  ['fallback', { ...ready, response: handoff.failures.invalid }],
  ['replay', { ...ready, response: ready.replay }],
  ['snapshotless', snapshotless], ['unsupported-notice', ready],
  ['history-detail', ready], ['history-unavailable', { ...ready, detail: handoff.legacy.chart }],
];
const gateScenarios = ['unsupported-notice', 'unsupported-notice-request-id',
  'unsupported-notice-retry', 'unsupported-notice-both', 'unsupported-notice-raw-input'].map(label => [label, ready]);

async function newScenario(label, row, width) {
  const context = await browser.newContext({ viewport: { width, height: 960 },
    serviceWorkers: 'block', locale: 'ko-KR', timezoneId: 'Asia/Seoul' });
  const page = await context.newPage();
  activePage = page;
  page.on('pageerror', error => report.pageErrors.push({ label, width, message: error.message }));
  await context.addInitScript(() => {
    localStorage.setItem('alphamate.devAuth.v1', JSON.stringify({ session_token: 'phase5-synthetic-session',
      user: { id: 'phase5-synthetic-user', display_name: '합성 검증', journal_storage_enabled: true } }));
  });
  await context.route('**/*', async route => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.origin === origin) return route.continue();
    if (url.origin !== 'http://127.0.0.1:8002') {
      report.externalRequests.push({ label, width, origin: url.origin, path: url.pathname });
      return route.abort('blockedbyclient');
    }
    const headers = { 'access-control-allow-origin': origin, 'access-control-allow-headers': '*',
      'access-control-allow-methods': 'GET,POST,OPTIONS', 'content-type': 'application/json' };
    if (request.method() === 'OPTIONS') return route.fulfill({ status: 204, headers });
    report.requests.push({ label, width, path: url.pathname, method: request.method(),
      displayContract: request.headers()['x-review-display-contract'] || null });
    let body = {};
    let status = 200;
    if (url.pathname === '/api/journal/trades') body = ready.detail.recent_trades_snapshot;
    else if (url.pathname === '/api/journal/entitlements') body = { plan: 'free',
      basic: { signup_remaining: 20, free_available_now: 20 }, advanced: { purchased_remaining: 20 } };
    else if (url.pathname === '/api/journal/review-history') body = [row.detail];
    else if (url.pathname.startsWith('/api/journal/review-history/')) body = row.detail;
    else if (url.pathname === '/api/journal/charts') body = ready.general;
    else if (url.pathname === '/api/journal/ai-review-once') {
      assert.equal(request.headers()['x-review-display-contract'], 'review-display.v1');
      body = row.response;
      if (label.startsWith('unsupported-notice')) {
        status = 426;
        body = { detail: { code: 'unsupported_review_display_client',
          message: label.endsWith('raw-input') ? 'RAW_BACKEND_INPUT' : 'AI 복기를 표시하려면 앱을 업데이트해 주세요.' } };
        headers['access-control-expose-headers'] = 'X-Request-ID, Retry-After';
        if (label.endsWith('request-id') || label.endsWith('both') || label.endsWith('raw-input')) headers['x-request-id'] = 'request-123';
        if (label.endsWith('retry') || label.endsWith('both') || label.endsWith('raw-input')) headers['retry-after'] = '15';
      }
    } else if (!['/api/journal/review', '/api/journal/review-once', '/api/auth/oauth-config',
      '/api/app/readiness', '/api/me/data-summary', '/api/journal/products', '/api/client-events'].includes(url.pathname)) {
      report.pageErrors.push({ label, width, message: `unhandled synthetic API ${url.pathname}` });
      return route.abort('blockedbyclient');
    }
    return route.fulfill({ status, headers, body: JSON.stringify(body) });
  });
  await page.goto(`${origin}/?view=journal`, { waitUntil: 'networkidle' });
  await page.locator('.journal-review-target-list input[type=radio]').first().check();
  await page.locator('.journal-ai-consent input').check();
  return { context, page };
}

async function checkScenario(label, row, width) {
  const { context, page } = await newScenario(label, row, width);
  try {
    if (label.startsWith('history-')) {
      await page.getByRole('button', { name: '복기 보관함', exact: true }).click();
      await page.locator('.review-history-list button:not(.journal-secondary)').first().click();
      if (label === 'history-unavailable') {
        await page.locator('.review-history-detail .journal-ai-document [role=status]').waitFor();
        assert.equal(await page.locator('.review-history-detail .journal-ai-document').innerText(), '복기 내용을 표시할 수 없습니다.');
        report.checks.push({ label, viewportWidth: width, passed: true, unavailable: true });
      } else {
        await inspectDom(page.locator('.review-history-detail .journal-ai-document .canonical-review-display'),
          row.detail.ai_review.display_snapshot, label, width);
      }
    } else {
      await page.getByRole('button', { name: label === 'live-advanced' ? '심화 복기' : '일반 복기', exact: true }).click();
      if (label.startsWith('unsupported-notice')) {
        await page.getByText('AI 복기 분석을 불러오지 못했습니다.', { exact: true }).waitFor();
        assert.equal(await page.locator('.journal-ai-review [role=status]').innerText(), 'AI 복기 분석을 불러오지 못했습니다.');
        const notice = page.getByText('AI 복기를 표시하려면 앱을 업데이트해 주세요.', { exact: true });
        await notice.waitFor();
        await notice.scrollIntoViewIfNeeded();
        const actual = await notice.evaluate(node => ({ text: node.textContent, visibleText: node.innerText,
          display: getComputedStyle(node).display, visibility: getComputedStyle(node).visibility,
          rect: node.getBoundingClientRect().toJSON(), viewportWidth: window.innerWidth }));
        assert.equal(actual.text, 'AI 복기를 표시하려면 앱을 업데이트해 주세요.');
        assert.equal(actual.visibleText, actual.text);
        assert.notEqual(actual.display, 'none');
        assert.equal(actual.visibility, 'visible');
        assert.ok(actual.rect.width > 0 && actual.rect.height > 0);
        assert.ok(actual.rect.left >= -1 && actual.rect.right <= actual.viewportWidth + 1);
        const visible = await page.locator('body').innerText();
        assert.ok(!visible.includes('RAW_BACKEND_INPUT') && !visible.includes('request-123') && !visible.includes('15초 뒤 다시 시도'));
        report.checks.push({ label, viewportWidth: width, passed: true, updateNotice: true, actual, rawReflection: false });
        await notice.screenshot({ path: join(artifactRoot, `${label}-${width}.png`) });
      } else if (label === 'snapshotless') {
        await page.locator('.journal-ai-document [role=status]').waitFor();
        assert.equal(await page.locator('.journal-ai-document').innerText(), '복기 내용을 표시할 수 없습니다.');
        assert.equal(await page.locator('.journal-ai-card, .journal-review-chart-block').count(), 0);
        report.checks.push({ label, viewportWidth: width, passed: true, unavailable: true, rawFallback: false });
      } else {
        await inspectDom(page.locator('.journal-ai-document .canonical-review-display'), row.response.display_snapshot, label, width);
        for (const [index, card] of (row.response.chart_display_snapshot?.chart_cards || []).entries()) {
          await inspectDom(page.locator('.journal-ai-card .canonical-review-display').nth(index), card.display, `${label}:chart-card-${index}`, width);
        }
        if (row.response.status !== 'error' && row.response.chart_display_snapshot?.charts.length) {
          await inspectDom(page.locator('.journal-review-chart-block .journal-chart-mode .canonical-review-display'),
            row.response.chart_display_snapshot.charts[0].header, `${label}:chart-header`, width);
        }
      }
    }
    const visible = await page.locator('body').innerText();
    assert.ok(!visible.includes('RAW_SUMMARY_FALLBACK_FORBIDDEN') && !visible.includes('RAW_STRUCTURED_FALLBACK_FORBIDDEN'));
    if (['live-basic', 'live-strong', 'history-detail'].includes(label)) {
      await page.screenshot({ path: join(artifactRoot, `${label}-${width}.png`), fullPage: true });
    }
    console.log(`BROWSER_PASS ${width} ${label}`);
  } finally { await context.close(); }
}

try {
  browser = await chromium.launch({ executablePath, headless: true,
    args: ['--disable-background-networking', '--disable-component-update',
      '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1'] });
  report.browserVersion = browser.version();
  for (const width of [1440, 390]) {
    for (const [label, row] of gateOnly ? gateScenarios : tooltipOnly ? [] : scenarios) await checkScenario(label, row, width);
  }
  // Trigger the real lightweight-charts crosshair and production tooltip root.
  for (const width of gateOnly ? [] : [1440, 390]) {
    for (const [label, row] of tooltipOnly ? [['marker-tooltip', ready], ['marker-tooltip-strong', strongTooltip]] : [['marker-tooltip', ready]]) {
    const { context, page } = await newScenario(label, row, width);
    try {
      await page.getByRole('button', { name: '일반 복기', exact: true }).click();
      const chart = page.locator('.journal-trade-chart');
      await chart.waitFor({ state: 'visible' });
      await chart.scrollIntoViewIfNeeded();
      const bounds = await chart.boundingBox();
      const tooltip = page.locator('.journal-marker-tooltip');
      for (let x = 12; x < bounds.width - 60; x += 12) {
        await page.mouse.move(bounds.x + x, bounds.y + 100);
        if (await tooltip.isVisible()) break;
      }
      assert.ok(await tooltip.isVisible(), 'real chart hover must show tooltip');
      for (const [index, marker] of row.snapshot.charts[0].markers.entries()) {
        await inspectDom(tooltip.locator('.canonical-review-display').nth(index), marker.tooltip, `${label}-${index}`, width);
      }
      await tooltip.screenshot({ path: join(artifactRoot, `${label}-${width}.png`) });
      if (tooltipOnly && label === 'marker-tooltip') await inspectLegacyTooltip(page, width);
      console.log(`BROWSER_PASS ${width} ${label}`);
    } finally { await context.close(); }
    }
  }
  assert.deepEqual(report.externalRequests, []);
  assert.deepEqual(report.pageErrors, []);
  report.passed = true;
} catch (error) {
  report.passed = false;
  report.error = error.message;
  if (activePage && !activePage.isClosed()) {
    await activePage.screenshot({ path: join(artifactRoot, 'failure-page.png'), fullPage: true }).catch(() => {});
  }
  console.error(error.message);
  process.exitCode = 1;
} finally {
  if (browser) { await browser.close(); report.browserClosed = true; }
  await new Promise(done => server.close(done));
  report.serverClosed = true;
  await writeFile(join(artifactRoot, 'browser-report.json'), JSON.stringify(report, null, 2));
}
