import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { flushSync } from 'react-dom';
import ts from 'typescript';

import { aiReviewChartSource } from '../src/utils/aiReviewChartSource.js';
import { basicReviewInput, captureReviewInput } from '../src/utils/basicReviewInput.js';
import { buildAiReviewIdempotencyKey } from '../src/utils/aiReviewIdempotency.js';
import { reviewDisplayHeaders, reviewDisplayFailureMessage } from '../src/utils/reviewDisplayContract.js';
import { installAxiosRequestIdMessages } from '../src/utils/apiErrorRequestId.js';
import CanonicalReviewRenderer from '../src/components/CanonicalReviewRenderer.js';
import { nodeEvidence, readRenderedDom, renderEvidence, textContent } from './review-render-evidence.js';
import { getTooltipPosition } from '../src/utils/chartLayout.js';
import { MARKET_UP, MARKET_DOWN, MARKET_UP_ALPHA, MARKET_DOWN_ALPHA } from '../src/theme/marketColors.js';

// Required actual outputs of generation, seal, route, synthetic storage,
// whole-record adapter and replay in a fresh H4 backend child. No expected-value fallback.
const handoff = JSON.parse(readFileSync(new URL('./fixtures/generated-review-chart-results.json', import.meta.url), 'utf8'));
assert.equal(handoff.passed, true);
const source = readFileSync(new URL('../src/components/TradingJournal.jsx', import.meta.url), 'utf8');
const ast = ts.createSourceFile('TradingJournal.jsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.JSX);
assert.deepEqual(ast.parseDiagnostics, []);
const journal = ast.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === 'TradingJournal');
assert.ok(journal);
const declarations = new Map(journal.body.statements.filter(ts.isVariableStatement)
  .flatMap(statement => statement.declarationList.declarations.map(declaration => [declaration.name.getText(ast), statement.getText(ast)])));

function compile(text, bindings, result) {
  const lowered = ts.transpileModule(text, {
    fileName: 'production.jsx', reportDiagnostics: true,
    compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React },
  });
  assert.deepEqual(lowered.diagnostics, []);
  return new Function(...Object.keys(bindings), `${lowered.outputText}\nreturn ${result};`)(...Object.values(bindings));
}

// Compile original AST declarations/subtrees. These harnesses supply I/O and
// state observers only; no chart selector, loader, tooltip or renderer is cloned.
function original(name, bindings) {
  assert.ok(declarations.has(name), `missing production declaration ${name}`);
  const scope = Object.fromEntries(Object.entries(bindings).filter(([key]) => key !== name));
  if (name === 'openReviewHistoryDetail') {
    let callback;
    function BindProductionCallback() {
      callback = compile(declarations.get(name), { ...scope, useCallback: React.useCallback }, name);
      return null;
    }
    renderToStaticMarkup(React.createElement(BindProductionCallback));
    return callback;
  }
  return compile(declarations.get(name), scope, name);
}
let cardExpression;
let liveExpression;
function findCards(node) {
  if (ts.isCallExpression(node) && node.expression.getText(ast) === 'aiChartSource.chart_cards.map') cardExpression = node.getText(ast);
  if (ts.isJsxElement(node) && node.openingElement.attributes.properties.some(attribute =>
    ts.isJsxAttribute(attribute) && attribute.name.text === 'className'
      && attribute.initializer?.text === 'journal-ai-review')) liveExpression = node.getText(ast);
  ts.forEachChild(node, findCards);
}
findCards(journal);
assert.ok(cardExpression);
assert.ok(liveExpression);

function canonicalProbe(observed) {
  return props => { observed.push(props); return React.createElement(CanonicalReviewRenderer, props); };
}

function surfaces(observed) {
  return observed.map(props => ({ document: props.document, surface: props.expectedSurface || 'body',
    defaultBody: props.expectedSurface === undefined,
    ...renderEvidence(renderToStaticMarkup(React.createElement(CanonicalReviewRenderer, props))) }));
}

const chartSource = readFileSync(new URL('../src/components/JournalTradeChart.jsx', import.meta.url), 'utf8');
const tooltipCss = readFileSync(new URL('../src/App.css', import.meta.url), 'utf8');
const chartAst = ts.createSourceFile('JournalTradeChart.jsx', chartSource, ts.ScriptTarget.Latest, true, ts.ScriptKind.JSX);
assert.deepEqual(chartAst.parseDiagnostics, []);
const chartDeclarations = chartAst.statements.filter(node => !ts.isImportDeclaration(node)).map(node => node.getText(chartAst)).join('\n');
const noop = () => {};
function actualChart(bindings = {}) {
  return compile(chartDeclarations, {
    exports: {}, React, useEffect: React.useEffect, useRef: React.useRef,
    CanonicalReviewRenderer, flushSync, createRoot: () => assert.fail('SSR must not create a DOM root'),
    createChart: () => assert.fail('SSR must not create an imperative chart'), createSeriesMarkers: noop,
    CandlestickSeries: 'candles', HistogramSeries: 'volume', LineSeries: 'line', CrosshairMode: { Magnet: 1 },
    MARKET_UP, MARKET_DOWN, MARKET_UP_ALPHA, MARKET_DOWN_ALPHA, getTooltipPosition,
    ...bindings,
  }, 'JournalTradeChart');
}

function harness(response, general = handoff.results[0].general) {
  const state = { aiReview: null, chartReview: general, activeChartTicker: '', details: false,
    activeReviewHistory: null, historyLoading: false, message: '' };
  const calls = [];
  const updates = [];
  const update = (field, value) => { state[field] = value; updates.push({ field, value }); };
  const axios = {
    async post(url, body, config) {
      calls.push({ url, body, config });
      if (url.endsWith('/ai-review-once')) return { data: response };
      if (url.endsWith('/charts-once')) return { data: general };
      if (url.endsWith('/review-once')) return { data: { summary: {}, by_symbol: [] } };
      assert.fail(`unexpected POST ${url}`);
    },
    async get(url, config) { calls.push({ url, config }); return { data: handoff.results[0].detail }; },
  };
  const bindings = {
    axios, apiBase: 'https://synthetic.invalid', trades: [{ id: 1 }], aiReviewType: 'basic', aiConsentAccepted: true,
    aiReviewInFlightRef: { current: false }, basicReviewFocusIndexRef: { current: 0 },
    captureReviewInput, aiReviewSourceRef: { current: null },
    setAiReviewSource: noop,
    reviewHistoryDetailRequestRef: original('reviewHistoryDetailRequestRef', { useRef: value => ({ current: value }) }),
    BASIC_REVIEW_FOCUSES: ['balanced'], DEV_TOOLS_ENABLED: false, DEV_ACCESS_PLAN: 'free',
    DEV_AD_REWARD_TOKEN: '', DEV_ENTITLEMENT_TOKEN: '', authHeaders: {},
    authSession: { session_token: 'synthetic', user: { journal_storage_enabled: true } },
    transientJournalMode: true, showCurrentReviewDetails: true, activeChartTicker: '',
    buildAiReviewIdempotencyKey, aiReviewChartSource, reviewDisplayHeaders, reviewDisplayFailureMessage,
    setMessage: value => update('message', value), setReview: noop, setAiLoading: noop,
    setAiReview: value => { state.aiReview = value; }, setChartReview: value => { state.chartReview = value; },
    setActiveChartTicker: value => update('activeChartTicker', value),
    setShowCurrentReviewDetails: value => { state.details = value; },
    setEntitlements: noop, setReviewAccessDialog: noop, loadEntitlements: noop,
    loadReviewHistory: noop, loadDataSummary: noop, setReviewHistoryLoading: value => update('historyLoading', value),
    setActiveReviewHistory: value => update('activeReviewHistory', value),
  };
  bindings.loadReviewContextForTrades = original('loadReviewContextForTrades', bindings);
  return { state, calls, updates, bindings, axios, run: original('loadAiReview', bindings), loadGeneral: original('loadChartReview', bindings) };
}

function renderImmediate(review, activeChartTicker = '') {
  const aiChartSource = aiReviewChartSource(review);
  const activeTradeChart = original('activeTradeChart', { aiChartSource, activeChartTicker });
  const observed = [];
  const ActualChart = actualChart();
  const ChartProbe = props => { observed.push(props); return React.createElement(ActualChart, props); };
  const view = original('renderSelectedTradeChart', {
    React, aiChartSource, activeTradeChart, tradeChartSectionRef: { current: null },
    setActiveChartTicker: noop, JournalTradeChart: ChartProbe, CanonicalReviewRenderer,
  })();
  const cards = compile(`const cards = ${cardExpression};`, { React, aiChartSource, CanonicalReviewRenderer }, 'cards');
  return { observed, html: renderToStaticMarkup(React.createElement(React.Fragment, null, view, cards)) };
}

function renderLiveResult(aiReview, aiLoading = false) {
  const observed = [];
  const view = compile(`const view = ${liveExpression};`, {
    React, aiReview, aiLoading, aiChartSource: aiReviewChartSource(aiReview), reviewAccessText: () => '',
    basicReviewInput, aiReviewSource: null, adLoading: false, aiConsentAccepted: true,
    deepenBasicReview: () => assert.fail('rendering must not execute advanced review'),
    CanonicalReviewRenderer: canonicalProbe(observed),
  }, 'view');
  const html = renderToStaticMarkup(view);
  const documents = surfaces(observed);
  for (const result of documents) assert.ok(html.includes(result.html));
  return { html, documents, body: documents.find(result => result.defaultBody) };
}

function renderHistory(record, reviewHistoryLoading = false, activeChartTicker = '', reviewHistory = []) {
  const observed = [];
  const canonicalObserved = [];
  const ActualChart = actualChart();
  const ChartProbe = props => { observed.push(props); return React.createElement(ActualChart, props); };
  const view = original('renderReviewHistoryArchive', {
    React, activeReviewHistory: record, reviewHistory, reviewHistoryLoading,
    activeChartTicker, setActiveChartTicker: noop,
    authSession: { user: { journal_storage_enabled: true } }, aiReviewChartSource,
    loadReviewHistory: noop, openReviewHistoryDetail: noop, deleteReviewHistoryItem: noop,
    restoreReviewHistoryTrades: noop, dateTimeText: value => value,
    CanonicalReviewRenderer: canonicalProbe(canonicalObserved), JournalTradeChart: ChartProbe,
  })();
  const html = renderToStaticMarkup(view);
  const documents = surfaces(canonicalObserved);
  for (const result of documents) assert.ok(html.includes(result.html));
  return { observed, html, documents, body: documents.find(result => result.defaultBody) };
}

function historyRequests() {
  const h = harness(null);
  const requests = new Map();
  h.axios.get = url => {
    h.calls.push({ url });
    return new Promise((resolve, reject) => requests.set(url.split('/').at(-1), { resolve, reject }));
  };
  return { ...h, requests, open: original('openReviewHistoryDetail', h.bindings) };
}

function noHistorySurface(h) {
  assert.equal(h.state.activeReviewHistory, null);
  assert.equal(h.state.activeChartTicker, '');
  const view = renderHistory(h.state.activeReviewHistory, h.state.historyLoading, h.state.activeChartTicker);
  assert.equal(view.observed.length, 0);
  assert.equal(view.body, undefined);
  assert.ok(!view.html.includes('journal-ai-card'));
}

function selectedHistory(h, record) {
  assert.strictEqual(h.state.activeReviewHistory, record);
  assert.equal(h.state.historyLoading, false);
  assert.equal(h.state.message, '');
  const view = renderHistory(h.state.activeReviewHistory, h.state.historyLoading, h.state.activeChartTicker);
  assert.strictEqual(view.observed[0].chartData, record.ai_review.chart_display_snapshot.charts[0]);
  assert.strictEqual(view.body.document, record.ai_review.display_snapshot);
  assert.equal(view.body.text, record.ai_review.display_snapshot.canonical_text);
  assert.ok(view.html.includes(record.ai_review.chart_display_snapshot.chart_cards[0].display.canonical_text));
}

const snapshotDocuments = [
  ['header', snapshot => snapshot.charts[0].header],
  ['tab', snapshot => snapshot.charts[0].tab],
  ['marker', snapshot => snapshot.charts[0].markers[0].label],
  ['tooltip', snapshot => snapshot.charts[0].markers[0].tooltip],
  ['card', snapshot => snapshot.chart_cards[0].display],
];

function corruptedReview(select, mutate) {
  const review = structuredClone(handoff.results[0].response);
  const snapshot = review.chart_display_snapshot;
  // A bad document in any position must also suppress other valid charts/cards.
  snapshot.charts.push({ ...structuredClone(snapshot.charts[0]), ticker: '000660' });
  snapshot.chart_cards.push(structuredClone(snapshot.chart_cards[0]));
  mutate(select(snapshot));
  return review;
}

async function rejectedSnapshot(review, label) {
  const h = harness(review);
  await h.run([{ id: 1 }]);
  assert.deepEqual(aiReviewChartSource(h.state.aiReview), { charts: [], chart_cards: [] }, label);
  const immediate = renderImmediate(h.state.aiReview);
  assert.equal(immediate.observed.length, 0, label);
  assert.equal(immediate.html, '', label);
  // Canonical history with separate safe legacy/general metadata cannot fallback.
  const history = renderHistory({ ...handoff.results[0].detail, ai_review: review });
  assert.equal(history.observed.length, 0, label);
  assert.ok(!history.html.includes('journal-ai-card'), label);
  assert.equal(h.calls.filter(call => call.url.endsWith('/charts-once')).length, 0, label);
}

function fixtureText(document, text) {
  document.blocks = [{ type: 'paragraph', runs: [{ type: 'text', text }], separator_after: '' }];
  document.canonical_text = text;
}

class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.style = {}; this.textContent = ''; this.clientWidth = 800; this.clientHeight = 430; }
  append(...nodes) { this.children.push(...nodes); }
  appendChild(node) { this.append(node); }
  replaceChildren(...nodes) { this.children = nodes; }
  remove() { this.removed = true; }
}
function chartEffect(chartData, approvedSnapshot = true) {
  const container = new Element('div');
  const evidence = { series: [], markers: null, crosshair: null, cleanup: null, documents: [] };
  const model = {
    addSeries(type) { const series = { type, setData(data) { evidence.series.push({ type, data }); } }; return series; },
    subscribeCrosshairMove(fn) { evidence.crosshair = fn; }, panes: () => [],
    timeScale: () => ({ fitContent: noop }), remove() { evidence.removed = true; },
  };
  const Chart = actualChart({
    useRef: () => ({ current: container }), useEffect: fn => { evidence.cleanup = fn(); },
    createChart: () => model, createSeriesMarkers: (_series, markers) => { evidence.markers = markers; },
    document: { createElement: tag => new Element(tag) },
    CanonicalReviewRenderer: canonicalProbe(evidence.documents),
    // Observe the external DOM-root boundary, executing actual React rendering
    // of the original production tooltip JSX and canonical component.
    createRoot: element => ({
      render(view) {
        evidence.tooltipHtml = renderToStaticMarkup(view);
        const dom = readRenderedDom(evidence.tooltipHtml);
        element.replaceChildren(...dom.children.map(node => ({ ...node, textContent: textContent(node) })));
      },
      unmount() { evidence.unmounted = true; element.replaceChildren(); },
    }),
  });
  Chart({ chartData, approvedSnapshot });
  evidence.crosshair({ time: chartData.candles[0].time, point: { x: 10, y: 10 } });
  evidence.tooltip = container.children[0];
  return evidence;
}

const unavailable = '복기 내용을 표시할 수 없습니다.';
const resultRows = [...handoff.results, ...handoff.body_results];

function verifyLegacyTooltipCss() {
  const rule = tooltipCss.match(/([^{}]*\.journal-marker-tooltip[^{}]*)\{\s*display:\s*block;\s*\}/);
  assert.ok(rule);
  assert.deepEqual(rule[1].split(',').map(selector => selector.trim()), [
    '.journal-marker-tooltip-section > strong', '.journal-marker-tooltip-section > span',
    '.journal-marker-tooltip-section > em',
  ]);
  const chart = structuredClone(handoff.results[0].snapshot.charts[0]);
  chart.markers = [
    { time: chart.candles[0].time, side: 'buy', tooltip: { label: '매수', count: 2, avg_price: 70200,
      total_quantity: 2, prices: [70000, 70400] } },
    { time: chart.candles[0].time, side: 'sell', tooltip: { label: '매도', count: 1, avg_price: 70900,
      total_quantity: 1, prices: [70900], profit_amount: 700, return_rate: 1 } },
  ];
  const effect = chartEffect(chart, false);
  assert.equal(effect.tooltip.style.display, 'block');
  assert.equal(effect.documents.length, 0);
  assert.deepEqual(effect.tooltip.children.map(section => section.children.map(node => [node.tag, node.textContent])), [
    [['strong', '매수 2건'], ['span', '평균 70,200원 · 수량 2'], ['em', '70,000, 70,400원']],
    [['strong', '매도'], ['span', '평균 70,900원 · 수량 1'], ['em', '70,900원'], ['b', '실현 +700원 · +1%']],
  ]);
  assert.deepEqual(effect.tooltip.children.map(section => section.className), [
    'journal-marker-tooltip-section buy', 'journal-marker-tooltip-section sell',
  ]);
  effect.cleanup();
  assert.equal(effect.tooltip.removed, true);
  assert.equal(effect.removed, true);
}

test('production basic and advanced AI requests declare exact display support and retain auth and idempotency', async () => {
  for (const row of handoff.results) {
    const h = harness(row.response);
    h.bindings.authHeaders.Authorization = 'Bearer synthetic';
    await h.run(undefined, row.review_type);
    const request = h.calls.find(call => call.url.endsWith('/ai-review-once'));
    assert.equal(request.body.review_type, row.review_type);
    assert.equal(request.config.headers['X-Review-Display-Contract'], 'review-display.v1');
    assert.equal(request.config.headers.Authorization, 'Bearer synthetic');
    assert.match(request.config.headers['X-Idempotency-Key'], /^ai-review-[a-z0-9]+-[a-z0-9]+$/);
    assert.equal(Object.keys(request.config.headers).filter(key => key.toLowerCase() === 'x-review-display-contract').length, 1);
  }
});

test('production history list and detail requests declare exact display support', async () => {
  const h = harness(null);
  h.axios.get = async (url, config) => {
    h.calls.push({ url, config });
    return { data: url.endsWith('/review-history') ? [handoff.results[0].detail] : handoff.results[0].detail };
  };
  const list = original('loadReviewHistory', { ...h.bindings, activeReviewHistory: null, setReviewHistory: noop });
  await list();
  await original('openReviewHistoryDetail', h.bindings)(handoff.results[0].detail.id);
  assert.equal(h.calls.length, 2);
  for (const request of h.calls) assert.deepEqual(request.config.headers, {
    Authorization: 'Bearer synthetic', 'X-Review-Display-Contract': 'review-display.v1',
  });
  assert.strictEqual(h.state.activeReviewHistory, handoff.results[0].detail);
});

test('production ordinary journal chart review and data summary requests have no display header', async () => {
  const h = harness(handoff.results[0].response);
  await h.loadGeneral(h.bindings.trades);
  await h.run();
  await original('loadDataSummary', { ...h.bindings, setDataSummary: noop })('synthetic');
  const requests = h.calls.filter(call => !call.url.endsWith('/ai-review-once'));
  assert.ok(requests.some(call => call.url.endsWith('/charts-once')));
  assert.ok(requests.some(call => call.url.endsWith('/review-once')));
  assert.ok(requests.some(call => call.url.endsWith('/data-summary')));
  for (const request of requests) assert.equal(request.config?.headers?.['X-Review-Display-Contract'], undefined);
});

test('production compatibility failures use fixed update notice without reflecting raw error values', async () => {
  const h = harness(null);
  const error = { response: { status: 426, data: { detail: {
    code: 'unsupported_review_display_client', message: 'RAW REQUEST HEADER',
  } } } };
  h.axios.post = h.axios.get = async () => { throw error; };
  const operations = [() => h.run(), () => original('openReviewHistoryDetail', h.bindings)('synthetic'),
    original('loadReviewHistory', { ...h.bindings, activeReviewHistory: null, setReviewHistory: noop }),
    original('handleExportAccountData', { ...h.bindings, setAuthLoading: noop })];
  for (const operation of operations) {
    await operation();
    assert.equal(h.state.message, 'AI 복기를 표시하려면 앱을 업데이트해 주세요.');
    assert.ok(!h.state.message.includes('RAW'));
  }
  assert.deepEqual(h.state.aiReview, { status: 'request_error' });
  assert.equal(h.state.activeReviewHistory, null);
});

test('installed production interceptor preserves gate code for all four actual display consumers', async () => {
  for (const headers of [{}, { 'x-request-id': 'request-123' }, { 'retry-after': '15' },
    { 'x-request-id': 'request-123', 'retry-after': '15' }]) {
    const h = harness(null);
    let rejected;
    installAxiosRequestIdMessages({ interceptors: { response: { use: (_fulfilled, handler) => { rejected = handler; } } } });
    const detail = Object.freeze({ code: 'unsupported_review_display_client', message: 'RAW BACKEND INPUT' });
    const error = { response: { status: 426, headers, data: Object.freeze({ detail }) } };
    h.axios.post = h.axios.get = () => rejected(error);
    const operations = [() => h.run(), () => original('openReviewHistoryDetail', h.bindings)('synthetic'),
      original('loadReviewHistory', { ...h.bindings, activeReviewHistory: null, setReviewHistory: noop }),
      original('handleExportAccountData', { ...h.bindings, setAuthLoading: noop })];
    for (const operation of operations) {
      await operation();
      assert.strictEqual(error.response.data.detail, detail);
      assert.equal(error.response.data.detail.code, 'unsupported_review_display_client');
      assert.equal(h.state.message, 'AI 복기를 표시하려면 앱을 업데이트해 주세요.');
      assert.ok(!h.state.message.includes('RAW') && !h.state.message.includes('request-123'));
    }
    assert.deepEqual(h.state.aiReview, { status: 'request_error' });
    assert.equal(h.state.activeReviewHistory, null);
  }
});

test('new frontend receiving old server snapshotless live and history responses never renders legacy summary', async () => {
  for (const row of handoff.results) {
    const oldReview = { ...row.response, summary: 'OLD SERVER LEGACY SUMMARY' };
    delete oldReview.display_snapshot;
    delete oldReview.chart_display_snapshot;
    const h = harness(oldReview);
    await h.run(undefined, row.review_type);
    const live = renderLiveResult(h.state.aiReview);
    assert.ok(live.html.includes('복기 내용을 표시할 수 없습니다.'));
    assert.ok(!live.html.includes('OLD SERVER LEGACY SUMMARY'));
    assert.deepEqual(aiReviewChartSource(h.state.aiReview).charts, []);
    const oldDetail = { ...row.detail, ai_review: oldReview };
    delete oldDetail.history_read_status;
    h.axios.get = async () => ({ data: oldDetail });
    await original('openReviewHistoryDetail', h.bindings)(row.detail.id);
    const history = renderHistory(h.state.activeReviewHistory);
    assert.ok(history.html.includes('복기 내용을 표시할 수 없습니다.'));
    assert.ok(!history.html.includes('OLD SERVER LEGACY SUMMARY'));
    assert.equal(h.calls.filter(call => call.url.endsWith('/charts-once')).length, 0);
  }
});

test('actual production live body plain and strong exactly match the approved route document', async () => {
  for (const row of handoff.body_results) {
    const h = harness(row.response);
    await h.run([{ id: 1 }], row.review_type);
    const live = renderLiveResult(h.state.aiReview);
    assert.strictEqual(live.body.document, row.response.display_snapshot);
    assert.equal(live.body.text, row.response.display_snapshot.canonical_text);
    assert.ok(live.body.text.includes('체결 기록을 확인합니다.'));
    const start = Array.from(live.body.text.slice(0, live.body.text.indexOf('체결 기록을 확인합니다.'))).length;
    assert.deepEqual(live.body.strongRanges, row.body_case === 'strong'
      ? [{ start, end: start + 5, text: '체결 기록' }] : []);
    const changed = renderLiveResult({ ...h.state.aiReview, summary: 'LEGACY_BODY_ONLY' });
    assert.equal(changed.html, live.html);
    assert.ok(!changed.html.includes('LEGACY_BODY_ONLY'));
    assert.equal(h.calls.filter(call => call.url.endsWith('/charts-once')).length, 0);
  }
});

test('actual live saved history detail export cache and replay share exact body and strong structure', () => {
  for (const row of resultRows) {
    const live = renderLiveResult(row.response).body;
    assert.deepEqual(row.saved.ai_review.display_snapshot, live.document);
    for (const review of [row.cache, row.replay]) {
      const body = renderLiveResult(review).body;
      assert.strictEqual(body.document, review.display_snapshot);
      assert.deepEqual(body.document, live.document);
      assert.equal(body.html, live.html);
      assert.equal(body.text, live.text);
      assert.deepEqual(body.strongRanges, live.strongRanges);
    }
    for (const record of [row.saved_admitted, row.detail, row.exported]) {
      const body = renderHistory(record).body;
      assert.strictEqual(body.document, record.ai_review.display_snapshot);
      assert.deepEqual(body.document, live.document);
      assert.equal(body.html, live.html);
      assert.equal(body.text, body.document.canonical_text);
      assert.deepEqual(body.strongRanges, live.strongRanges);
    }
    assert.deepEqual(row.replay_effects, { model: 0, charge: 0, refund: 0, history: 0, provider: 0, market: 0, charts_once: 0 });
  }
});

test('production body preserves Markdown-like plain text and mid-word strong without legacy parsing', () => {
  const review = structuredClone(handoff.body_results[0].response);
  fixtureText(review.display_snapshot, '현재는 매**수** 추천합니다. * [참고](url)');
  review.summary = '현재는 매**수** 추천합니다. [참고](url)';
  const plain = renderLiveResult(review).body;
  assert.equal(plain.text, '현재는 매**수** 추천합니다. * [참고](url)');
  assert.deepEqual(plain.strongRanges, []);
  review.display_snapshot.blocks[0].runs = [
    { type: 'text', text: '현재는 매' }, { type: 'strong', text: '수' }, { type: 'text', text: ' 추천합니다.' },
  ];
  review.display_snapshot.canonical_text = '현재는 매수 추천합니다.';
  const strong = renderLiveResult(review).body;
  assert.equal(strong.text, '현재는 매수 추천합니다.');
  assert.deepEqual(strong.strongRanges, [{ start: 5, end: 6, text: '수' }]);
  for (const name of ['AiReviewSummary', 'ReviewInlineText', 'reviewDisplayText', 'aiReviewFormat']) assert.ok(!source.includes(name));
});

test('invalid or missing production body with a normal legacy summary has zero fallback body chart or card', () => {
  const valid = handoff.body_results[0].response;
  const mutations = [
    document => { document.schema_version = 'review-display.v99'; },
    document => { document.blocks = []; },
    document => { document.blocks = {}; },
    document => { document.blocks[0].type = 'unknown'; },
    document => { document.blocks[0].runs = []; },
    document => { document.blocks[0].runs = {}; },
    document => { document.blocks[0].runs[0].type = 'unknown'; },
    document => { document.blocks[0].runs[0].text = {}; },
    document => { document.canonical_text = 'UNAPPROVED'; },
    document => { document.unknown = 'UNAPPROVED'; },
    document => { document.blocks[0].unknown = 'UNAPPROVED'; },
    document => { document.blocks[0].runs[0].unknown = 'UNAPPROVED'; },
    document => { document.surface = 'chart_card'; },
  ];
  const documents = [undefined, null, {}, ...mutations.map(mutate => {
    const document = structuredClone(valid.display_snapshot);
    mutate(document);
    return document;
  })];
  for (const document of documents) {
    const review = { ...valid, summary: '기존 복기 내용입니다.', display_snapshot: document };
    if (document === undefined) delete review.display_snapshot;
    const before = JSON.stringify(review);
    const live = renderLiveResult(review);
    const history = renderHistory({ ...handoff.body_results[0].detail, ai_review: review });
    for (const view of [live, history]) {
      assert.equal(view.body.text, unavailable);
      assert.deepEqual(view.body.strongRanges, []);
      assert.ok(!view.html.includes(review.summary));
      assert.ok(!view.html.includes('UNAPPROVED'));
      assert.ok(!view.html.includes('journal-ai-card'));
    }
    assert.equal(history.observed.length, 0);
    assert.equal(renderImmediate(review).html, '');
    assert.equal(JSON.stringify(review), before);
  }
});

test('production body keeps every block separator whitespace Unicode and literal label without rebuilding', () => {
  const review = structuredClone(handoff.results[0].response);
  review.display_snapshot = {
    schema_version: 'review-display.v1', surface: 'body', blocks: [
      { type: 'heading', runs: [{ type: 'text', text: '  제목 e\u0301 😀' }], separator_after: '\n\n' },
      { type: 'list_item', runs: [{ type: 'text', text: '7) [데이터 확인]  MA 10 ' },
        { type: 'strong', text: '체결 기록' }], separator_after: '\t\n' },
      { type: 'divider', runs: [{ type: 'text', text: '───' }], separator_after: '\n' },
      { type: 'paragraph', runs: [{ type: 'text', text: '<script>&  끝  ' }], separator_after: ' \n' },
    ], canonical_text: '  제목 e\u0301 😀\n\n7) [데이터 확인]  MA 10 체결 기록\t\n───\n<script>&  끝   \n',
  };
  review.summary = '변환된 legacy 문장';
  review.basic = { verdict: 'semantic 재조립 금지' };
  const live = renderLiveResult(review).body;
  const history = renderHistory({ ...handoff.results[0].detail, ai_review: review }).body;
  assert.equal(live.text, review.display_snapshot.canonical_text);
  assert.equal(history.html, live.html);
  assert.deepEqual(live.blocks, ['heading', 'list_item', 'divider', 'paragraph']);
  assert.deepEqual(live.strong, ['체결 기록']);
  assert.ok(!live.html.includes('<script>'));
});

test('actual production history body and card clear across A to B invalid to valid and valid to invalid', async () => {
  const a = handoff.body_results.find(row => row.body_case === 'strong').detail;
  const b = handoff.results[1].detail;
  const invalid = structuredClone(a);
  invalid.ai_review.display_snapshot.canonical_text = 'UNAPPROVED';
  invalid.ai_review.summary = '기존 복기 내용입니다.';
  const h = historyRequests();
  for (const [id, record] of [['A', a], ['B', b], ['invalid', invalid], ['valid', a], ['invalid-again', invalid]]) {
    const pending = h.open(id);
    noHistorySurface(h);
    h.requests.get(id).resolve({ data: record });
    await pending;
    const view = renderHistory(h.state.activeReviewHistory);
    if (record === invalid) {
      assert.equal(view.body.text, unavailable);
      assert.deepEqual(view.body.strongRanges, []);
      assert.equal(view.observed.length, 0);
      assert.ok(!view.html.includes('journal-ai-card'));
      assert.ok(!view.html.includes(invalid.ai_review.summary));
    } else selectedHistory(h, record);
  }
});

test('whole-record unavailable history cannot render even an injected valid body snapshot', () => {
  const record = { ...handoff.results[0].detail, history_read_status: 'unavailable' };
  const view = renderHistory(record);
  assert.equal(view.body.text, unavailable);
  assert.equal(view.observed.length, 0);
  assert.ok(!view.html.includes('journal-ai-card'));
});

test('transport failures use fixed frontend notice and recover to the approved production body', async () => {
  const row = handoff.body_results[1];
  const h = harness(row.response);
  const post = h.axios.post;
  h.axios.post = async () => { throw { response: { status: 500, data: { detail: 'UNAPPROVED' } } }; };
  await h.run([{ id: 1 }]);
  assert.deepEqual(h.state.aiReview, { status: 'request_error' });
  assert.equal(h.state.message, 'AI 분석을 불러오지 못했습니다.');
  const failed = renderLiveResult(h.state.aiReview);
  assert.equal(failed.body, undefined);
  assert.equal(renderEvidence(failed.html).text, 'AI 복기 분석을 불러오지 못했습니다.');
  assert.equal(renderImmediate(h.state.aiReview).html, '');
  for (const data of [null, undefined]) {
    h.axios.post = async () => ({ data });
    await h.run([{ id: 1 }]);
    assert.deepEqual(h.state.aiReview, { status: 'request_error' });
    assert.equal(renderEvidence(renderLiveResult(h.state.aiReview).html).text, 'AI 복기 분석을 불러오지 못했습니다.');
    assert.equal(renderImmediate(h.state.aiReview).html, '');
  }
  h.axios.post = post;
  await h.run([{ id: 1 }]);
  assert.equal(renderLiveResult(h.state.aiReview).body.text, row.response.display_snapshot.canonical_text);
});

test('original account export preserves canonical snapshot for the same history production renderer', async () => {
  for (const row of resultRows) {
    let exportedBlob;
    const calls = [];
    const exportData = { review_history: [row.exported] };
    const exportAccount = original('handleExportAccountData', {
      authSession: { session_token: 'synthetic' }, apiBase: 'https://synthetic.invalid',
      axios: { async get(url, config) { calls.push({ url, config }); return { data: exportData }; } },
      reviewDisplayHeaders, reviewDisplayFailureMessage,
      setAuthLoading: noop, setMessage: noop, File: undefined, navigator: {}, Blob,
      URL: { createObjectURL(blob) { exportedBlob = blob; return 'blob:synthetic'; }, revokeObjectURL: noop },
      document: { createElement: () => ({ click: noop, remove: noop }), body: { appendChild: noop } },
      window: { setTimeout: callback => callback() },
    });
    await exportAccount();
    assert.deepEqual(calls, [{ url: 'https://synthetic.invalid/api/me/export-data', config: {
      headers: { Authorization: 'Bearer synthetic', 'X-Review-Display-Contract': 'review-display.v1' },
    } }]);
    const exported = JSON.parse(await exportedBlob.text()).review_history[0];
    assert.deepEqual(exported.ai_review.display_snapshot, row.response.display_snapshot);
    assert.equal(renderHistory(exported).body.html, renderLiveResult(row.response).body.html);
  }
});

test('actual approved card header tab and DOM tooltip preserve canonical strong nodes and text identity', () => {
  const review = structuredClone(handoff.results[0].response);
  for (const [, select] of snapshotDocuments) {
    const document = select(review.chart_display_snapshot);
    document.blocks = [{ type: 'paragraph', runs: [{ type: 'strong', text: '체결 기록' },
      { type: 'text', text: '을 확인합니다.  \n' }], separator_after: '' }];
    document.canonical_text = '체결 기록을 확인합니다.  \n';
  }
  const chart = review.chart_display_snapshot.charts[0];
  review.chart_display_snapshot.charts.push({ ...structuredClone(chart), ticker: '000660' });
  const before = JSON.stringify(review);
  const live = renderLiveResult(review);
  const history = renderHistory({ ...handoff.results[0].detail, ai_review: review });
  for (const view of [live, history]) {
    for (const result of view.documents.filter(result => result.surface !== 'body')) {
      assert.equal(result.text, result.document.canonical_text);
      assert.deepEqual(result.strongRanges, [{ start: 0, end: 5, text: '체결 기록' }]);
    }
  }
  const selected = renderImmediate(review);
  assert.ok(selected.html.includes('<strong>체결 기록</strong>'));
  const effect = chartEffect(chart);
  const tooltip = nodeEvidence(effect.tooltip.children[0]);
  assert.equal(tooltip.text, chart.markers[0].tooltip.canonical_text);
  assert.deepEqual(tooltip.strongRanges, [{ start: 0, end: 5, text: '체결 기록' }]);
  assert.strictEqual(effect.documents[0].document, chart.markers[0].tooltip);
  assert.equal(effect.documents[0].expectedSurface, 'marker_tooltip');
  assert.equal(effect.markers[0].text, chart.markers[0].label.canonical_text);
  assert.equal(JSON.stringify(review), before);
  effect.cleanup();
  assert.equal(effect.unmounted, true);
  assert.equal(effect.tooltip.removed, true);
});

test('new AI completion renders the actual approved chart without charts-once', async () => {
  for (const row of handoff.results) {
    const h = harness(row.response, row.general);
    await h.run([{ id: 1 }], row.review_type);
    assert.strictEqual(aiReviewChartSource(h.state.aiReview), row.response.chart_display_snapshot);
    const view = renderImmediate(h.state.aiReview);
    assert.strictEqual(view.observed[0].chartData, row.response.chart_display_snapshot.charts[0]);
    assert.equal(view.observed[0].approvedSnapshot, true);
    assert.ok(view.html.includes(row.snapshot.charts[0].header.canonical_text));
    assert.ok(view.html.includes(row.snapshot.chart_cards[0].display.canonical_text));
    assert.equal(h.calls.filter(call => call.url.endsWith('/charts-once')).length, 0);
  }
});

test('different synthetic charts-once cannot replace immediate saved detail or replay charts', async () => {
  for (const row of handoff.results) {
    assert.notDeepEqual(row.general.charts, row.snapshot.charts);
    assert.notDeepEqual(row.saved.chart_snapshot.charts, row.snapshot.charts);
    for (const review of [row.response, row.replay]) {
      const h = harness(review, row.general);
      await h.run([{ id: 1 }], row.review_type);
      assert.deepEqual(renderImmediate(h.state.aiReview).observed[0].chartData, row.snapshot.charts[0]);
      assert.equal(h.calls.filter(call => call.url.endsWith('/charts-once')).length, 0);
    }
    assert.deepEqual(renderHistory(row.detail).observed[0].chartData, row.snapshot.charts[0]);
    assert.deepEqual(row.saved.ai_review.chart_display_snapshot, row.snapshot);
  }
});

test('real backend replay has zero additional model provider market chart billing or history effects', () => {
  for (const row of handoff.results) {
    assert.deepEqual(row.replay_effects, { model: 0, charge: 0, refund: 0, history: 0, provider: 0, market: 0, charts_once: 0 });
    assert.deepEqual(row.replay.chart_display_snapshot, row.response.chart_display_snapshot);
    assert.equal(row.replay.access.idempotent_replay, true);
  }
});

test('ordinary pre-AI chart loader still queries general charts-once', async () => {
  const h = harness(handoff.results[0].response);
  await h.loadGeneral([{ id: 1 }]);
  assert.equal(h.calls.filter(call => call.url.endsWith('/charts-once')).length, 1);
  assert.strictEqual(h.state.chartReview, handoff.results[0].general);
});

test('a pending ordinary chart load finishing after AI cannot change its source', async () => {
  const row = handoff.results[0];
  const h = harness(row.response);
  let finish;
  const post = h.axios.post;
  h.axios.post = (url, body) => url.endsWith('/charts-once')
    ? new Promise(resolve => { finish = resolve; }) : post(url, body);
  const pending = h.loadGeneral([{ id: 1 }]);
  await h.run([{ id: 1 }]);
  finish({ data: row.general });
  await pending;
  assert.strictEqual(h.state.chartReview, row.general);
  assert.strictEqual(renderImmediate(h.state.aiReview).observed[0].chartData, row.response.chart_display_snapshot.charts[0]);
});

test('unsafe invalid and compatibility AI failures show zero chart or card fallback', async () => {
  for (const review of Object.values(handoff.failures)) {
    const h = harness(review);
    await h.run([{ id: 1 }]);
    const view = renderImmediate(h.state.aiReview);
    assert.equal(view.observed.length, 0);
    assert.equal(view.html, '');
    assert.equal(h.calls.filter(call => call.url.endsWith('/charts-once')).length, 0);
    assert.equal(h.calls.filter(call => call.url.endsWith('/review-once')).length, 0);
  }
});

test('whole-record adapter rejects unsafe legacy chart tooltip trade and unknown canonical in real history UI', async () => {
  for (const [name, record] of Object.entries(handoff.legacy).filter(([name]) => name !== 'safe')) {
    assert.equal(record.history_read_status, 'unavailable', name);
    const view = renderHistory(record);
    assert.equal(view.observed.length, 0, name);
    assert.ok(!view.html.includes('매수 추천'), name);
    const h = harness(null);
    const restore = original('restoreReviewHistoryTrades', { ...h.bindings, activeReviewHistory: record });
    await restore();
    assert.equal(h.calls.length, 0, name);
  }
});

test('admitted safe legacy history renders its existing chart and tooltip documents', () => {
  const record = handoff.legacy.safe;
  assert.equal(record.history_read_status, 'adapted');
  const view = renderHistory(record);
  assert.strictEqual(view.observed[0].chartData, record.chart_snapshot.charts[0]);
  assert.strictEqual(view.body.document, record.ai_review.display_snapshot);
  assert.equal(view.body.text, record.ai_review.display_snapshot.canonical_text);
  for (const result of view.documents) assert.equal(result.text, result.document.canonical_text);
  const card = view.documents.find(result => result.document === record.ai_review.chart_reviews[0].display_snapshot);
  assert.ok(card);
  assert.equal(card.surface, 'body');
  const effect = chartEffect(view.observed[0].chartData);
  assert.equal(effect.markers[0].text, record.chart_snapshot.charts[0].markers[0].display_snapshot.canonical_text);
  assert.equal(effect.tooltip.children[0].textContent, record.chart_snapshot.charts[0].markers[0].tooltip.display_snapshot.canonical_text);
  assert.equal(effect.documents[0].expectedSurface, 'body');
  assert.strictEqual(effect.documents[0].document, record.chart_snapshot.charts[0].markers[0].tooltip.display_snapshot);
  effect.cleanup();
  assert.equal(effect.removed, true);
});

test('actual JournalTradeChart uses sealed marker and tooltip text without number formatting', () => {
  verifyLegacyTooltipCss();
  for (const row of handoff.results) {
    const chart = row.response.chart_display_snapshot.charts[0];
    const before = JSON.stringify(chart);
    const effect = chartEffect(chart);
    assert.deepEqual(effect.markers.map(marker => marker.text), chart.markers.map(marker => marker.label.canonical_text));
    assert.deepEqual(effect.tooltip.children.map(section => section.textContent), chart.markers.map(marker => marker.tooltip.canonical_text));
    assert.equal(JSON.stringify(chart), before);
    effect.cleanup();
    assert.equal(effect.removed, true);
  }
});

test('operational metadata additions leave chart content and rendered surface identical', () => {
  for (const row of handoff.results) {
    const changed = { ...row.response, review_history_id: 999, access: { ...row.response.access, idempotent_replay: true } };
    assert.strictEqual(aiReviewChartSource(changed), row.response.chart_display_snapshot);
    assert.equal(renderImmediate(changed).html, renderImmediate(row.response).html);
    assert.equal(renderImmediate(row.replay).html, renderImmediate(row.response).html);
  }
});

test('missing or invalid live snapshot never falls back to raw AI extras or general charts', async () => {
  for (const snapshot of [undefined, null, {}, { charts: [] }]) {
    const review = { ...handoff.results[0].response, chart_display_snapshot: snapshot,
      chart_snapshot: handoff.results[0].general.charts[0], chart_reviews: [{ title: '원시 제목', detail: '원시 설명' }] };
    if (snapshot === undefined) delete review.chart_display_snapshot;
    const h = harness(review);
    await h.run([{ id: 1 }]);
    assert.equal(renderImmediate(h.state.aiReview).html, '');
    assert.equal(h.calls.filter(call => call.url.endsWith('/charts-once')).length, 0);
  }
});

test('history detail request failure clears the previously selected approved chart', async () => {
  const h = harness(null);
  h.state.activeReviewHistory = handoff.results[0].detail;
  h.axios.get = async () => { throw new Error('synthetic detail failure'); };
  await original('openReviewHistoryDetail', h.bindings)(1);
  assert.equal(h.state.activeReviewHistory, null);
  assert.equal(renderHistory(h.state.activeReviewHistory).observed.length, 0);
  assert.equal(h.calls.filter(call => call.url.endsWith('/charts-once')).length, 0);
  for (const data of [null, undefined]) {
    h.state.activeReviewHistory = handoff.results[0].detail;
    h.axios.get = async () => ({ data });
    await original('openReviewHistoryDetail', h.bindings)(1);
    noHistorySurface(h);
    assert.equal(h.state.message, '저장된 복기를 불러오지 못했습니다.');
  }
});

test('history A then B with B success before A success keeps only B and ignores stale finally', async () => {
  const h = historyRequests();
  h.state.activeReviewHistory = handoff.results[0].detail;
  h.state.activeChartTicker = '005930';
  const a = h.open('A');
  noHistorySurface(h);
  const b = h.open('B');
  noHistorySurface(h);
  h.requests.get('B').resolve({ data: handoff.results[1].detail });
  await b;
  selectedHistory(h, handoff.results[1].detail);
  const count = h.updates.length;
  h.requests.get('A').resolve({ data: handoff.results[0].detail });
  await a;
  assert.equal(h.updates.length, count);
  selectedHistory(h, handoff.results[1].detail);
});

test('history A then B with A success before B failure never exposes stale A', async () => {
  const h = historyRequests();
  const a = h.open('A');
  const b = h.open('B');
  noHistorySurface(h);
  const count = h.updates.length;
  h.requests.get('A').resolve({ data: handoff.results[0].detail });
  await a;
  assert.equal(h.updates.length, count);
  assert.equal(h.state.historyLoading, true);
  noHistorySurface(h);
  h.requests.get('B').reject({ response: { data: { detail: 'latest B failed' } } });
  await b;
  noHistorySurface(h);
  assert.equal(h.state.historyLoading, false);
  assert.equal(h.state.message, '저장된 복기를 불러오지 못했습니다.');
});

test('history A then B with A failure before B success preserves B loading and clears old errors', async () => {
  const h = historyRequests();
  h.state.message = 'previous failure';
  const a = h.open('A');
  const b = h.open('B');
  const count = h.updates.length;
  h.requests.get('A').reject({ response: { data: { detail: 'stale A failed' } } });
  await a;
  assert.equal(h.updates.length, count);
  assert.equal(h.state.historyLoading, true);
  assert.equal(h.state.message, '');
  noHistorySurface(h);
  h.requests.get('B').resolve({ data: handoff.results[1].detail });
  await b;
  selectedHistory(h, handoff.results[1].detail);
});

test('rapid history selections clear every old chart card and ignore stale failure after latest success', async () => {
  const h = historyRequests();
  h.state.activeReviewHistory = handoff.results[0].detail;
  h.state.activeChartTicker = '005930';
  const pending = ['A', 'B', 'C'].map(id => {
    const request = h.open(id);
    noHistorySurface(h);
    return request;
  });
  h.requests.get('A').resolve({ data: handoff.results[0].detail });
  await pending[0];
  noHistorySurface(h);
  assert.equal(h.state.historyLoading, true);
  h.requests.get('C').resolve({ data: handoff.results[1].detail });
  await pending[2];
  selectedHistory(h, handoff.results[1].detail);
  const count = h.updates.length;
  h.requests.get('B').reject({ response: { data: { detail: 'stale B failed' } } });
  await pending[1];
  assert.equal(h.updates.length, count);
  selectedHistory(h, handoff.results[1].detail);
  assert.equal(h.calls.filter(call => call.url.endsWith('/charts-once')).length, 0);
});

test('unknown v99 canonical chart documents including the reported card fail closed before JSX', async () => {
  for (const [name, select] of snapshotDocuments) {
    await rejectedSnapshot(corruptedReview(select, document => { document.schema_version = 'review-display.v99'; }), name);
  }
  const reported = { ...handoff.results[0].response, chart_display_snapshot: {
    charts: [], chart_cards: [{ display: { schema_version: 'review-display.v99', blocks: [], canonical_text: 'UNAPPROVED' } }],
  } };
  await rejectedSnapshot(reported, 'reported v99 empty-block card');
  assert.ok(!renderHistory({ ...handoff.results[0].detail, ai_review: reported }).html.includes('UNAPPROVED'));
});

test('malformed block and run in any canonical chart document suppress the whole surface', async () => {
  const mutations = [
    document => { document.blocks = []; },
    document => { document.blocks = {}; },
    document => { document.blocks[0].type = 'unknown'; },
    document => { document.blocks[0].runs = {}; },
    document => { document.blocks[0].runs = []; },
    document => { document.blocks[0].runs[0].type = 'unknown'; },
    document => { document.blocks[0].runs[0].text = { nested: 'UNAPPROVED' }; },
  ];
  for (const [name, select] of snapshotDocuments) {
    for (const mutate of mutations) await rejectedSnapshot(corruptedReview(select, mutate), name);
  }
});

test('canonical text mismatch in any chart document suppresses every chart and card', async () => {
  for (const [name, select] of snapshotDocuments) {
    await rejectedSnapshot(corruptedReview(select, document => { document.canonical_text = 'UNAPPROVED'; }), name);
  }
});

test('unknown document block or run fields fail the existing closed canonical contract', async () => {
  const mutations = [
    document => { document.unknown = 'UNAPPROVED'; },
    document => { document.blocks[0].unknown = 'UNAPPROVED'; },
    document => { document.blocks[0].runs[0].unknown = 'UNAPPROVED'; },
  ];
  for (const [name, select] of snapshotDocuments) {
    for (const mutate of mutations) await rejectedSnapshot(corruptedReview(select, mutate), name);
  }
});

test('canonical chart documents must have the surface approved for their position', async () => {
  for (const [name, select] of snapshotDocuments) {
    await rejectedSnapshot(corruptedReview(select, document => { document.surface = 'body'; }), name);
  }
});

test('valid snapshot recovers after invalid snapshot in actual AI and history detail loaders', async () => {
  const row = handoff.results[0];
  const invalid = corruptedReview(snapshotDocuments[4][1], document => { document.schema_version = 'review-display.v99'; });
  const h = harness(invalid);
  await h.run([{ id: 1 }]);
  assert.equal(renderImmediate(h.state.aiReview).html, '');
  const post = h.axios.post;
  h.axios.post = (url, body) => url.endsWith('/ai-review-once') ? Promise.resolve({ data: row.response }) : post(url, body);
  await h.run([{ id: 1 }]);
  assert.strictEqual(renderImmediate(h.state.aiReview).observed[0].chartData, row.response.chart_display_snapshot.charts[0]);
  const history = historyRequests();
  const first = history.open('invalid');
  history.requests.get('invalid').resolve({ data: { ...row.detail, ai_review: invalid } });
  await first;
  assert.equal(renderHistory(history.state.activeReviewHistory).observed.length, 0);
  const next = history.open('valid');
  noHistorySurface(history);
  history.requests.get('valid').resolve({ data: row.detail });
  await next;
  selectedHistory(history, row.detail);
  assert.equal(h.calls.filter(call => call.url.endsWith('/charts-once')).length, 0);
});

test('invalid snapshot after valid snapshot leaves zero prior chart or card in actual production views', async () => {
  const row = handoff.results[0];
  const invalid = corruptedReview(snapshotDocuments[3][1], document => { document.canonical_text = 'UNAPPROVED'; });
  const h = harness(row.response);
  await h.run([{ id: 1 }]);
  assert.equal(renderImmediate(h.state.aiReview).observed.length, 1);
  const post = h.axios.post;
  h.axios.post = (url, body) => url.endsWith('/ai-review-once') ? Promise.resolve({ data: invalid }) : post(url, body);
  await h.run([{ id: 1 }]);
  assert.equal(h.state.activeChartTicker, '');
  assert.equal(renderImmediate(h.state.aiReview).html, '');
  const history = historyRequests();
  history.state.activeReviewHistory = row.detail;
  history.state.activeChartTicker = '005930';
  const next = history.open('invalid');
  noHistorySurface(history);
  history.requests.get('invalid').resolve({ data: { ...row.detail, ai_review: invalid } });
  await next;
  const view = renderHistory(history.state.activeReviewHistory);
  assert.equal(view.observed.length, 0);
  assert.ok(!view.html.includes('journal-ai-card'));
  assert.ok(!view.html.includes('UNAPPROVED'));
  assert.equal(h.calls.filter(call => call.url.endsWith('/charts-once')).length, 0);
});

test('snapshot whitespace names periods cards and tooltips are not normalized or rebuilt', () => {
  const review = structuredClone(handoff.results[0].response);
  const chart = review.chart_display_snapshot.charts[0];
  fixtureText(chart.header, '  승인  주기\n승인 기간  ');
  fixtureText(chart.tab, '  승인  이름  ');
  fixtureText(chart.markers[0].label, '  승인 B  ');
  fixtureText(chart.markers[0].tooltip, '  승인 평균\n숫자와 별도 문구  ');
  fixtureText(review.chart_display_snapshot.chart_cards[0].display, '  승인 제목:  승인 상세  ');
  review.chart_display_snapshot.charts.push({ ...chart, ticker: '000660' });
  const view = renderImmediate(review);
  assert.ok(view.html.includes(chart.header.canonical_text));
  assert.ok(view.html.includes(chart.tab.canonical_text));
  assert.ok(view.html.includes(review.chart_display_snapshot.chart_cards[0].display.canonical_text));
  const effect = chartEffect(chart);
  assert.equal(effect.markers[0].text, chart.markers[0].label.canonical_text);
  assert.equal(effect.tooltip.children[0].textContent, chart.markers[0].tooltip.canonical_text);
  effect.cleanup();
});

test('new history list and detail titles render the identical backend approved document for synthetic names', () => {
  const rows = handoff.history_titles.filter(row => row.case === 'new');
  assert.equal(rows.length, 3);
  for (const row of rows) {
    const before = JSON.stringify(row);
    const view = renderHistory(row.detail, false, '', [row.listed]);
    const titles = view.documents.filter(result => result.document === row.listed.display_snapshot
      || result.document === row.detail.display_snapshot);
    assert.equal(titles.length, 2);
    assert.strictEqual(titles[0].document, row.listed.display_snapshot);
    assert.strictEqual(titles[1].document, row.detail.display_snapshot);
    assert.deepEqual(titles[0].document, titles[1].document);
    assert.equal(titles[0].html, titles[1].html);
    assert.equal(titles[0].text, row.detail.display_snapshot.canonical_text);
    assert.equal(titles[0].text, titles[1].text);
    assert.ok(titles[0].text.includes(row.saved.name));
    assert.deepEqual(row.detail.ai_review.chart_display_snapshot, row.snapshot);
    const chart = row.detail.ai_review.chart_display_snapshot.charts[0];
    // Expose the tab controls with two synthetic tickers while retaining the
    // actual backend-approved documents unchanged, including the tab document.
    const multi = { ...row.detail, ai_review: { ...row.detail.ai_review, chart_display_snapshot: {
      ...row.detail.ai_review.chart_display_snapshot, charts: [chart, { ...chart, ticker: '000660' }],
    } } };
    const tabs = renderHistory(multi, false, '', [row.listed]).documents.filter(result => result.surface === 'chart_tab');
    assert.equal(tabs.length, 2);
    for (const tab of tabs) {
      assert.strictEqual(tab.document, chart.tab);
      assert.deepEqual(tab.document, row.snapshot.charts[0].tab);
      assert.equal(tab.text, chart.tab.canonical_text);
    }
    const chartless = { ...row.detail, ai_review: { ...row.detail.ai_review,
      chart_display_snapshot: { charts: [], chart_cards: [] } } };
    const noChart = renderHistory(chartless, false, '', [row.listed]);
    assert.equal(noChart.observed.length, 0);
    assert.equal(noChart.documents[1].html, titles[1].html);
    assert.equal(JSON.stringify(row), before);
  }
});

test('legacy canonical adapted and unavailable history titles and tabs preserve adapter document identity', () => {
  const rows = handoff.history_titles.filter(row => row.case !== 'new');
  assert.equal(rows.length, 7);
  for (const row of rows) {
    const before = JSON.stringify(row);
    const charts = aiReviewChartSource(row.detail.ai_review, row.detail).charts;
    for (const ticker of charts.length ? charts.map(chart => chart.ticker) : ['']) {
      const view = renderHistory(row.detail, false, ticker, [row.listed]);
      assert.strictEqual(view.documents[0].document, row.listed.display_snapshot);
      assert.strictEqual(view.documents[1].document, row.detail.display_snapshot);
      assert.equal(view.documents[0].text, row.detail.display_snapshot.canonical_text);
      assert.equal(view.documents[0].html, view.documents[1].html);
      for (const result of view.documents.filter(result => result.document)) {
        assert.equal(result.text, result.document.canonical_text);
      }
      for (const chart of charts) {
        const uses = view.documents.filter(result => result.document === chart.display_snapshot);
        assert.equal(uses.length, chart.ticker === ticker ? 2 : 1);
        for (const use of uses) assert.equal(use.surface, 'body');
      }
      if (row.case === 'legacy_unavailable') assert.equal(view.observed.length, 0);
    }
    assert.equal(JSON.stringify(row), before);
  }
});

test('history title and legacy tab sinks never fall back to raw names or rebuild invalid documents', () => {
  const row = handoff.history_titles.find(row => row.case === 'legacy_adapted');
  const poison = 'RAW_NAME_DO_NOT_RENDER  **원시** e\u0301 😀';
  const changed = structuredClone(row);
  changed.listed.name = changed.detail.name = poison;
  changed.listed.ticker = changed.detail.ticker = 'RAW_TICKER_DO_NOT_RENDER';
  for (const chart of changed.detail.chart_snapshot.charts) chart.name = poison;
  const view = renderHistory(changed.detail, false, '', [changed.listed]);
  assert.equal(view.html, renderHistory(row.detail, false, '', [row.listed]).html);
  assert.ok(!textContent(readRenderedDom(view.html)).includes(poison));
  const unavailable = '복기 내용을 표시할 수 없습니다.';
  for (const mutate of [
    () => undefined,
    document => ({ ...document, surface: 'history_title' }),
    document => ({ ...document, canonical_text: 'UNAPPROVED_TITLE' }),
    document => ({ ...document, blocks: [] }),
  ]) {
    const invalid = structuredClone(changed);
    invalid.listed.display_snapshot = mutate(invalid.listed.display_snapshot);
    invalid.detail.display_snapshot = mutate(invalid.detail.display_snapshot);
    for (const chart of invalid.detail.chart_snapshot.charts) chart.display_snapshot = mutate(chart.display_snapshot);
    const failed = renderHistory(invalid.detail, false, '', [invalid.listed]);
    for (const result of failed.documents.filter(result => !result.defaultBody)) {
      assert.equal(result.text, unavailable);
    }
    assert.ok(!textContent(readRenderedDom(failed.html)).includes(poison));
    assert.ok(!failed.html.includes('UNAPPROVED_TITLE'));
    assert.ok(!failed.html.includes('RAW_TICKER_DO_NOT_RENDER'));
  }
  const historySource = declarations.get('renderReviewHistoryArchive');
  assert.doesNotMatch(historySource, /item\.name|activeReviewHistory\.name|chart\.name/);
});
