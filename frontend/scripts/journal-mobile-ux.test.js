import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ts from 'typescript';
import CanonicalReviewRenderer from '../src/components/CanonicalReviewRenderer.js';
import { aiReviewChartSource } from '../src/utils/aiReviewChartSource.js';
import { buildAiReviewIdempotencyKey } from '../src/utils/aiReviewIdempotency.js';
import { reviewDisplayHeaders, reviewDisplayFailureMessage } from '../src/utils/reviewDisplayContract.js';
import { renderEvidence } from './review-render-evidence.js';

const appSource = readFileSync(new URL('../src/App.jsx', import.meta.url), 'utf8');
const journalSource = readFileSync(new URL('../src/components/TradingJournal.jsx', import.meta.url), 'utf8');
const cssSource = readFileSync(new URL('../src/App.css', import.meta.url), 'utf8');
const vectors = JSON.parse(readFileSync(new URL('./fixtures/review-display-v1.json', import.meta.url), 'utf8'));
const ast = ts.createSourceFile('TradingJournal.jsx', journalSource, ts.ScriptTarget.Latest, true, ts.ScriptKind.JSX);
assert.deepEqual(ast.parseDiagnostics, []);
const journal = ast.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === 'TradingJournal');
assert.ok(journal);
const declarations = new Map(journal.body.statements.filter(ts.isVariableStatement)
  .flatMap(statement => statement.declarationList.declarations.map(declaration => [declaration.name.getText(ast), statement.getText(ast)])));
let liveExpression;
function findLiveBody(node) {
  if (ts.isJsxElement(node) && node.openingElement.attributes.properties.some(attribute =>
    ts.isJsxAttribute(attribute) && attribute.name.text === 'className'
      && attribute.initializer?.text === 'journal-ai-review')) liveExpression = node.getText(ast);
  ts.forEachChild(node, findLiveBody);
}
findLiveBody(journal);
assert.ok(liveExpression);

// Execute original production AST/JSX with synthetic I/O; never rebuild review text.
function compileProduction(source, bindings, result) {
  const compiled = ts.transpileModule(source, { fileName: 'production.jsx', reportDiagnostics: true,
    compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React } });
  assert.deepEqual(compiled.diagnostics, []);
  return new Function(...Object.keys(bindings), `${compiled.outputText}\nreturn ${result};`)(...Object.values(bindings));
}

function approvedResponse(document, reviewType = 'basic') {
  return { status: 'ready', source: 'openai', review_type: reviewType, review_history_id: 'synthetic-history',
    display_snapshot: document, summary: 'RAW_LEGACY_SUMMARY_DO_NOT_RENDER',
    structured_review: { summary: 'RAW_STRUCTURED_REVIEW_DO_NOT_RENDER' },
    chart_reviews: [{ title: 'RAW_CHART_TITLE_DO_NOT_RENDER', detail: 'RAW_CHART_DETAIL_DO_NOT_RENDER' }] };
}

function renderProductionReview(aiReview) {
  const observed = [];
  function ObserveCanonical(props) {
    observed.push(props);
    return React.createElement(CanonicalReviewRenderer, props);
  }
  const view = compileProduction(`const view = ${liveExpression};`, {
    React, aiReview, aiLoading: false, aiChartSource: aiReviewChartSource(aiReview),
    reviewAccessText: () => '', CanonicalReviewRenderer: ObserveCanonical,
  }, 'view');
  const html = renderToStaticMarkup(view);
  const body = observed.find(props => props.expectedSurface === undefined);
  assert.ok(body, 'actual production JSX must use the canonical body renderer');
  const bodyHtml = renderToStaticMarkup(React.createElement(CanonicalReviewRenderer, body));
  assert.ok(html.includes(bodyHtml));
  for (const raw of ['RAW_LEGACY_SUMMARY', 'RAW_STRUCTURED_REVIEW', 'RAW_CHART_TITLE', 'RAW_CHART_DETAIL']) {
    assert.ok(!html.includes(raw), raw);
  }
  return { ...renderEvidence(bodyHtml), html, document: body.document };
}

test('account management is reachable from both primary views', () => {
  assert.match(appSource, /className="mobile-app-account"[\s\S]*?onClick=\{openAccountPanel\}/);
  assert.match(appSource, /accountReturnViewRef/);
  assert.doesNotMatch(appSource, /activeView === 'journal' \? \([\s\S]{0,180}mobile-app-account/);
});

test('mobile chart controls use compact named grid areas', () => {
  assert.match(appSource, /controls-candles/);
  assert.match(appSource, /controls-count/);
  assert.match(cssSource, /grid-template-areas:[\s\S]*?"candles count"[\s\S]*?"period scale"/);
});

test('review UI hides internal model ids and consent versions', () => {
  assert.doesNotMatch(journalSource, /activeReviewHistory\.model/);
  assert.doesNotMatch(journalSource, /현재 동의 안내 버전/);
  assert.doesNotMatch(journalSource, /currentConsentVersion/);
  assert.match(journalSource, /동의일 \$\{consentRecordedAt\.slice\(0, 10\)\}/);
  assert.match(journalSource, /<h3>AI 복기<\/h3>/);
});

test('trade time supports native selection and direct numeric entry', () => {
  assert.match(journalSource, /directTimeEntry/);
  assert.match(journalSource, /inputMode=\{directTimeEntry \? 'numeric'/);
  assert.match(journalSource, /normalizeDirectTime/);
});

test('account data export uses Android share sheet and explains the backup location', () => {
  assert.match(journalSource, /navigator\.share/);
  assert.match(journalSource, /application\/json/);
  assert.match(journalSource, /link\.download = filename/);
  assert.match(journalSource, /내 파일 또는 Files/);
  assert.match(journalSource, /PC나 웹에서는 보통 다운로드 폴더/);
  assert.doesNotMatch(journalSource, /JSON 형식의 내 데이터 파일/);
});

test('saved review can restore only its selected trade episode for another review', () => {
  assert.match(journalSource, /restoreReviewHistoryTrades/);
  assert.match(journalSource, /recent_trades_snapshot/);
  assert.match(journalSource, /reviewTradesForGroup/);
  assert.match(journalSource, /preferredGroup\?\.trades/);
  assert.match(journalSource, /setJournalSubView\('review'\)/);
});

test('AI review sends only the explicitly selected trade episode', () => {
  assert.match(journalSource, /복기할 매매 선택/);
  assert.match(journalSource, /selectedReviewGroupKey/);
  assert.match(journalSource, /selectedReviewTrades/);
  assert.match(journalSource, /loadAiReview\(selectedReviewTrades, 'advanced'/);
  assert.match(journalSource, /const loadAiReview = async \(nextTrades = trades/);
  assert.match(journalSource, /trades: nextTrades/);
  assert.doesNotMatch(journalSource, /loadAiReview\(trades, 'advanced'/);
});

test('mobile entitlement balances remain in a compact three-column grid', () => {
  assert.match(cssSource, /\.journal-entitlement-grid \{[\s\S]*?grid-template-columns: repeat\(3, minmax\(0, 1fr\)\)/);
});

test('ad reward and Pro subscription policies use a scan-friendly hierarchy', () => {
  assert.match(journalSource, /className="journal-ad-policy-main"/);
  assert.match(journalSource, /className="journal-policy-reward"/);
  assert.match(journalSource, /className="journal-policy-condition"/);
  assert.match(journalSource, /className="journal-policy-chip"/);
  assert.match(journalSource, /className="journal-product-copy"/);
  assert.match(journalSource, /일반 35회 \+ 심화 25회 · 광고 제거/);
  assert.match(cssSource, /\.journal-ad-policy-main \.journal-policy-reward[\s\S]*?font-size: 17px/);
  assert.match(cssSource, /\.journal-product-copy \{[\s\S]*?display: grid/);
});

test('advanced review shortage opens a Korean pass dialog instead of an inline AI error', () => {
  assert.match(journalSource, /err\.response\?\.status === 402/);
  assert.match(journalSource, /reviewType === 'advanced' \? 'advanced' : 'basic'/);
  assert.match(journalSource, /심화 복기권이 필요합니다/);
  assert.match(journalSource, /onClick=\{startAdvancedReview\}/);
  assert.match(journalSource, /showReviewPasses/);
});

test('journal notices use a Korean popup and never render raw messages inline', () => {
  assert.match(journalSource, /toKoreanUserMessage/);
  assert.match(journalSource, /className="journal-notice-backdrop"/);
  assert.match(journalSource, /role="alertdialog"/);
  assert.doesNotMatch(journalSource, /className="journal-message"/);
  assert.doesNotMatch(cssSource, /\.journal-message\s*\{/);
});

test('advanced review terminology and rewarded-ad ticket action are user-facing', () => {
  assert.doesNotMatch(journalSource, /심층/);
  assert.match(journalSource, /signup_advanced: '무료 심화 복기권'/);
  assert.match(journalSource, /handleRewardedAdAdvancedTicket/);
  assert.match(journalSource, /\/api\/journal\/ad-reward-claim/);
  assert.match(journalSource, /\/privacy/);
});

test('reviewer access is backend-gated and does not expose credentials in config', () => {
  assert.match(journalSource, /reviewAccessStatus\?\.enabled/);
  assert.match(journalSource, /\/api\/auth\/review-login/);
  assert.match(journalSource, /심사용 로그인/);
  assert.match(journalSource, /review_id: reviewAccessId\.trim\(\)/);
  assert.match(journalSource, /password: reviewAccessPassword/);
  assert.doesNotMatch(journalSource, /reviewAccessPassword.*localStorage/);
  assert.match(journalSource, /!isReviewAccount && \(DEV_TOOLS_ENABLED \|\| billingStatus\.native\)/);
});

test('mobile header uses a graphical wordmark and masks scrolling content', () => {
  assert.match(appSource, /function AppWordmark\(\)/);
  assert.match(appSource, /<img src=\{appIcon\}/);
  assert.match(appSource, /const USE_STOCKBODA_WORDMARK = APP_NAME === 'StockBoda'/);
  assert.match(appSource, /stockboda-logo-horizontal-dark\.png/);
  assert.match(appSource, /className="mobile-app-brand-logo"/);
  assert.match(appSource, /<h2 className="sidebar-title">\{APP_NAME\}<\/h2>/);
  assert.match(cssSource, /\.mobile-app-brand img \{[\s\S]*?drop-shadow/);
  assert.match(cssSource, /\.mobile-app-brand img\.mobile-app-brand-logo \{[\s\S]*?background: transparent/);
  assert.match(cssSource, /\.theme-sidebar-fixed \{[\s\S]*?margin: -12px -12px 0;[\s\S]*?background: #131722/);
  assert.match(cssSource, /\.mobile-app-bar > \* \{[\s\S]*?z-index: 1/);
});

test('theme and chart divider follows the collapsible mobile sidebar', () => {
  assert.match(cssSource, /\.app-container\.themes-view \.sidebar \{[\s\S]*?border-bottom: 2px solid #44506a/);
});

test('general review reruns use a fresh request while rapid double taps stay locked', () => {
  assert.match(journalSource, /BASIC_REVIEW_FOCUSES/);
  assert.match(journalSource, /if \(aiReviewInFlightRef\.current\) return/);
  assert.match(journalSource, /aiReviewInFlightRef\.current = true/);
  assert.match(journalSource, /aiReviewInFlightRef\.current = false/);
  assert.match(journalSource, /analysis_focus: analysisFocus/);
});

test('general review balance distinguishes immediate free uses from rewarded-ad capacity', () => {
  assert.match(journalSource, /free_available_now/);
  assert.match(journalSource, /rewarded_ad_available/);
  assert.match(journalSource, /setReviewAccessDialog\(reviewType === 'advanced' \? 'advanced' : 'basic'\)/);
  assert.match(journalSource, /광고 보고 일반 복기/);
});

test('rewarded review waits for server-side verification without consuming it while polling', () => {
  assert.match(journalSource, /\/api\/journal\/ad-reward-status/);
  assert.match(journalSource, /waitForRewardedAdStatus\('basic_review'\)/);
  assert.match(journalSource, /waitForRewardedAdStatus\('advanced_ticket_progress'\)/);
  assert.match(journalSource, /getRewardedAdStatus\('basic_review'\)/);
});

test('saved journal entry does not reveal stock details until a review is selected or completed', () => {
  assert.match(journalSource, /setShowCurrentReviewDetails\(false\)/);
  assert.match(journalSource, /showCurrentReviewDetails && <section className="journal-panel">/);
});

test('successful AI review is not replaced by a failed follow-up refresh', async () => {
  assert.match(journalSource, /Promise\.allSettled\(followUpRefreshes\)/);
  for (const reviewType of ['basic', 'advanced']) {
    const vector = vectors.valid.find(value => value.id === 'normal_bold');
    assert.ok(vector);
    const response = approvedResponse(structuredClone(vector.document), reviewType);
    const before = JSON.stringify(response);
    const state = { aiReview: null, details: false, loading: false, message: '' };
    const calls = [];
    const bindings = {
      axios: { async post(url) {
        if (url.endsWith('/ai-review-once')) { calls.push('approved response'); return { data: response }; }
        if (url.endsWith('/review-once')) { calls.push('failed statistics'); throw new Error('synthetic statistics failure'); }
        assert.fail(`unexpected POST ${url}`);
      } },
      apiBase: 'https://synthetic.invalid', trades: [{ id: 1 }], aiReviewType: reviewType, aiConsentAccepted: true,
      aiReviewInFlightRef: { current: false }, basicReviewFocusIndexRef: { current: 0 },
      BASIC_REVIEW_FOCUSES: ['balanced'], DEV_TOOLS_ENABLED: false, DEV_ACCESS_PLAN: 'free',
      DEV_AD_REWARD_TOKEN: '', DEV_ENTITLEMENT_TOKEN: '', authHeaders: { Authorization: 'Bearer synthetic' },
      authSession: { session_token: 'synthetic' }, buildAiReviewIdempotencyKey, aiReviewChartSource,
      reviewDisplayHeaders, reviewDisplayFailureMessage,
      setAiReview: value => { state.aiReview = value; }, setAiLoading: value => { state.loading = value; },
      setShowCurrentReviewDetails: value => { state.details = value; },
      setMessage: value => { state.message = value; }, setActiveChartTicker: () => {},
      setReview: () => assert.fail('failed statistics must not publish data'), setEntitlements: () => {},
      setReviewAccessDialog: () => assert.fail('ready response must not open access dialog'),
      loadEntitlements: () => assert.fail('ready response must not enter transport failure'),
      loadReviewHistory: async () => { calls.push('failed history refresh'); throw new Error('synthetic history failure'); },
      loadDataSummary: async () => { calls.push('failed data refresh'); throw new Error('synthetic data failure'); },
    };
    bindings.loadReviewContextForTrades = compileProduction(declarations.get('loadReviewContextForTrades'), bindings, 'loadReviewContextForTrades');
    const load = compileProduction(declarations.get('loadAiReview'), bindings, 'loadAiReview');
    await load([{ id: 1 }], reviewType);
    assert.deepEqual(calls, ['approved response', 'failed statistics', 'failed history refresh', 'failed data refresh']);
    assert.strictEqual(state.aiReview, response);
    assert.strictEqual(state.aiReview.display_snapshot, response.display_snapshot);
    assert.equal(state.details, true);
    assert.equal(state.loading, false);
    assert.equal(state.message, '');
    assert.equal(bindings.aiReviewInFlightRef.current, false);
    const rendered = renderProductionReview(state.aiReview);
    assert.strictEqual(rendered.document, response.display_snapshot);
    assert.equal(rendered.text, vector.expected_canonical_text);
    assert.deepEqual(rendered.strong, ['체결 기록']);
    assert.equal(JSON.stringify(response), before);
  }
});

test('AI review loading is prominent and selected chart follows trade selection', () => {
  assert.match(journalSource, /className="journal-ai-loading" role="status" aria-live="polite"/);
  assert.match(journalSource, /AI 복기 분석 중/);
  assert.doesNotMatch(journalSource, /심화 복기 비교 분석 중/);

  const selectionIndex = journalSource.indexOf('복기할 매매 선택');
  const actionIndex = journalSource.indexOf('journal-review-actions');
  const chartRenderIndex = journalSource.lastIndexOf('renderSelectedTradeChart()');
  assert.ok(selectionIndex >= 0);
  assert.ok(actionIndex > selectionIndex);
  assert.ok(chartRenderIndex > actionIndex);
});

test('approved review output keeps canonical text and hides consumed one-time trial balances', () => {
  assert.doesNotMatch(journalSource, /\b(?:AiReviewSummary|reviewDisplayText|parseAiReviewSummary|parseAiReviewDocument)\b/);
  const prefix = '[데이터 확인] 매';
  const expected = `${prefix}수 **그대로** [합리적 추론]\n  첫 문단\n\n\t둘째  문단`;
  const document = { schema_version: vectors.schema_version, surface: 'body', blocks: [
    { type: 'paragraph', runs: [{ type: 'text', text: prefix }, { type: 'strong', text: '수' },
      { type: 'text', text: ' **그대로** [합리적 추론]\n  첫 문단' }], separator_after: '\n\n' },
    { type: 'paragraph', runs: [{ type: 'text', text: '\t둘째  문단' }], separator_after: '' },
  ], canonical_text: expected };
  const response = approvedResponse(document);
  const before = JSON.stringify(response);
  const rendered = renderProductionReview(response);
  assert.strictEqual(rendered.document, document);
  assert.equal(rendered.text, expected);
  assert.deepEqual(rendered.blocks, ['paragraph', 'paragraph']);
  assert.deepEqual(rendered.strongRanges, [{ start: [...prefix].length, end: [...prefix].length + 1, text: '수' }]);
  assert.equal(JSON.stringify(response), before);
  const mismatch = { ...document, canonical_text: 'UNAPPROVED_TEXT' };
  for (const invalid of [undefined, null, {}, mismatch, { ...document, schema_version: 'review-display.v99' }]) {
    const unavailable = renderProductionReview({ ...response, display_snapshot: invalid });
    assert.equal(unavailable.text, '복기 내용을 표시할 수 없습니다.');
    assert.deepEqual(unavailable.strong, []);
    assert.ok(!unavailable.html.includes('UNAPPROVED_TEXT'));
    assert.ok(!unavailable.html.includes('journal-ai-card'));
  }
  assert.match(journalSource, /signup_advanced: '무료 심화 복기권'/);
  assert.match(journalSource, /advanced\.signup_remaining/);
});

test('review picker shows recent trades, supports search, and QA requests carry the target trade id', () => {
  assert.match(journalSource, /filterReviewTradeGroups/);
  assert.match(journalSource, /reviewTargetQuery/);
  assert.match(journalSource, /reviewTargetFrom/);
  assert.match(journalSource, /reviewTargetTo/);
  assert.match(journalSource, /visibleReviewTradeGroups/);
  assert.match(journalSource, /target_trade_id: options\.targetTradeId \|\| null/);
  assert.match(journalSource, /targetTradeId: selectedReviewGroup\?\.targetTradeId/);
  assert.doesNotMatch(journalSource, /setSelectedReviewGroupKey\(reviewTradeGroups\[0\]\.key\)/);
  assert.doesNotMatch(journalSource, /reviewTargetPickerOpen/);
  assert.doesNotMatch(journalSource, /className="journal-advice"/);
});

test('account changes clear the previous account journal workspace before loading tenant data', () => {
  assert.match(journalSource, /const resetJournalWorkspace = \(\) =>/);
  assert.match(journalSource, /setTrades\(\[\]\)/);
  assert.match(journalSource, /setReviewHistory\(\[\]\)/);
  assert.match(journalSource, /setSelectedReviewGroupKey\(''\)/);
  assert.ok((journalSource.match(/resetJournalWorkspace\(\)/g) || []).length >= 4);
});

test('review archive entry uses a throttled interstitial policy', () => {
  assert.match(journalSource, /shouldShowReviewHistoryInterstitial/);
  assert.match(journalSource, /maybeShowReviewHistoryInterstitial/);
  assert.match(journalSource, /REVIEW_HISTORY_AD_ENTRY_COUNT_KEY/);
  assert.match(journalSource, /REVIEW_HISTORY_AD_LAST_SHOWN_KEY/);
});
