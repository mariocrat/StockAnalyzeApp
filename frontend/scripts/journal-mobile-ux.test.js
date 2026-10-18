import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createContext, runInContext } from 'node:vm';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ts from 'typescript';
import CanonicalReviewRenderer from '../src/components/CanonicalReviewRenderer.js';
import ReviewBodyRenderer from '../src/components/ReviewBodyRenderer.js';
import { aiReviewChartSource } from '../src/utils/aiReviewChartSource.js';
import { basicReviewInput, captureReviewInput } from '../src/utils/basicReviewInput.js';
import { buildAiReviewIdempotencyKey } from '../src/utils/aiReviewIdempotency.js';
import { reviewDisplayHeaders, reviewDisplayFailureMessage } from '../src/utils/reviewDisplayContract.js';
import { renderEvidence } from './review-render-evidence.js';
import { brokerReviewTradeIssue, prepareBrokerReviewInput } from '../src/utils/brokerReviewInput.js';
import { BROKER_STATEMENT_MESSAGES, BROKER_STATEMENT_STATUS, REVIEW_TIME_VALIDATION_MESSAGES,
  createTradeTimeState, formatTradeDateTime, formatTradeNumber, parseBrokerStatement,
  setTradeTimeUnknownState, sortTradesByDateDesc, tradeSideLabel, updateTradeTimeState,
  validateTradeTimesForReview } from '../src/utils/brokerImport.js';
import { buildReviewTradeGroups, reviewTradesForGroup } from '../src/utils/reviewTradeSelection.js';

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
const initializers = new Map(journal.body.statements.filter(ts.isVariableStatement)
  .flatMap(statement => statement.declarationList.declarations.map(declaration => [declaration.name.getText(ast), declaration.initializer])));
let liveExpression;
let prepareButtonExpression;
let directInputExpression;
let brokerInputExpression;
let selectedReviewExpression;
let selectionExpression;
let basicChoiceExpression;
let advancedChoiceExpression;
let deepenExpression;
function findLiveBody(node) {
  if (ts.isJsxElement(node) && node.openingElement.attributes.properties.some(attribute =>
    ts.isJsxAttribute(attribute) && attribute.name.text === 'className'
      && attribute.initializer?.text === 'journal-ai-review')) liveExpression = node.getText(ast);
  if (ts.isJsxElement(node) && node.openingElement.attributes.properties.some(attribute =>
    ts.isJsxAttribute(attribute) && attribute.name.text === 'className'
      && attribute.initializer?.text === 'journal-review-selection')) {
    let parent = node.parent;
    while (parent && !ts.isJsxExpression(parent)) parent = parent.parent;
    assert.ok(parent?.expression);
    selectionExpression = parent.expression.getText(ast);
  }
  if (ts.isJsxSelfClosingElement(node) && node.tagName.getText(ast) === 'input') {
    const attributes = node.attributes.properties;
    const name = attributes.find(attribute => ts.isJsxAttribute(attribute) && attribute.name.text === 'name');
    const value = attributes.find(attribute => ts.isJsxAttribute(attribute) && attribute.name.text === 'value');
    if (name?.initializer?.text === 'review-depth') {
      if (value?.initializer?.text === 'basic') basicChoiceExpression = node.getText(ast);
      if (value?.initializer?.text === 'advanced') advancedChoiceExpression = node.getText(ast);
    }
  }
  if (ts.isJsxElement(node) && node.openingElement.tagName.getText(ast) === 'button') {
    const click = node.openingElement.attributes.properties.find(attribute =>
      ts.isJsxAttribute(attribute) && attribute.name.text === 'onClick');
    const expression = click?.initializer?.expression;
    if (expression?.getText(ast) === 'prepareImportedTrades') prepareButtonExpression = node.getText(ast);
    if (expression?.getText(ast).includes("setJournalInputMode('direct')")) directInputExpression = node.getText(ast);
    if (expression?.getText(ast).includes("setJournalInputMode('broker')")) brokerInputExpression = node.getText(ast);
    if (expression?.getText(ast) === 'startSelectedReview') selectedReviewExpression = node.getText(ast);
    if (expression?.getText(ast) === 'deepenBasicReview') deepenExpression = node.getText(ast);
  }
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

// Like the H4 OAuth harness, use an isolated VM namespace, not Function parameters.
// Execute only original AST expressions: no injected declarations or mock handler names.
function expressionInContext(expression, context) {
  const compiled = ts.transpileModule(`(${expression})`, { fileName: 'production-expression.jsx', reportDiagnostics: true,
    compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React } });
  assert.deepEqual(compiled.diagnostics, []);
  return runInContext(compiled.outputText, context, { timeout: 1000 });
}

function handlerInContext(name, context) {
  const initializer = initializers.get(name);
  assert.ok(initializer && ts.isArrowFunction(initializer), name);
  return expressionInContext(initializer.getText(ast), context);
}

function syntheticContext(values) {
  return createContext(values, { codeGeneration: { strings: false, wasm: false } });
}

test('broker file admission enforces 25MiB before extraction and renders incomplete tables without transfer', async () => {
  const source = readFileSync(new URL('../src/components/BrokerImport.jsx', import.meta.url), 'utf8');
  const fileAst = ts.createSourceFile('BrokerImport.jsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.JSX);
  assert.deepEqual(fileAst.parseDiagnostics, []);
  const component = fileAst.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === 'BrokerImport');
  const declaration = component.body.statements.filter(ts.isVariableStatement)
    .flatMap(node => Array.from(node.declarationList.declarations)).find(node => node.name.getText(fileAst) === 'handleFileChange');
  const pdfCheck = fileAst.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === 'isPdfFile');
  const size = fileAst.statements.filter(ts.isVariableStatement)
    .flatMap(node => Array.from(node.declarationList.declarations)).find(node => node.name.getText(fileAst) === 'MAX_PDF_BYTES');
  let state;
  let reads = 0;
  let extractions = 0;
  const header = ['거래일자', '거래구분', '종목명(종목코드)', '거래수량', '단가'];
  const items = header.map((str, index) => ({ str, x: index * 100, y: 100 }));
  for (const [y, quantity] of [[80, '2'], [60, '불명']]) {
    items.push(...['2026.09.02', '구매', 'KODEX 200(A069500)', quantity, '7,830']
      .map((str, index) => ({ str, x: index * 100, y })));
  }
  const extraction = { text: '토스증권 원화 거래내역', pageCount: 1, pages: [{ pageNumber: 1, items }] };
  const context = syntheticContext({
    setState: value => { state = typeof value === 'function' ? value(state) : value; },
    extractPdfText: async () => { extractions += 1; return extraction; }, parseBrokerStatement,
    createTradeTimeState: () => ({ tradeTime: null, timeUnknown: true }),
    LocalPdfPasswordRequiredError: class extends Error {},
  });
  context.MAX_PDF_BYTES = expressionInContext(size.initializer.getText(fileAst), context);
  context.isPdfFile = expressionInContext(pdfCheck.getText(fileAst), context);
  const handle = expressionInContext(declaration.initializer.getText(fileAst), context);
  const event = bytes => ({ target: { value: 'selected', files: [{ name: 'synthetic.pdf', type: 'application/pdf', size: bytes,
    arrayBuffer: async () => { reads += 1; return new ArrayBuffer(0); } }] } });
  assert.equal(context.MAX_PDF_BYTES, 25 * 1024 * 1024);
  await handle(event(context.MAX_PDF_BYTES + 1));
  assert.equal(state.status, 'error');
  assert.match(state.message, /25MB/);
  assert.equal(reads, 0);
  assert.equal(extractions, 0);
  await handle(event(context.MAX_PDF_BYTES));
  assert.equal(reads, 1);
  assert.equal(extractions, 1);
  assert.equal(state.statementStatus, BROKER_STATEMENT_STATUS.TOSS_INCOMPLETE);
  assert.equal(state.trades.length, 0);
  let incomplete;
  function find(node) {
    if (ts.isJsxExpression(node) && node.expression?.getText(fileAst).includes('BROKER_STATEMENT_STATUS.TOSS_INCOMPLETE')) incomplete = node.expression.getText(fileAst);
    ts.forEachChild(node, find);
  }
  find(component);
  assert.ok(incomplete);
  const html = renderToStaticMarkup(expressionInContext(incomplete, syntheticContext({ React, state,
    BROKER_STATEMENT_STATUS, BROKER_STATEMENT_MESSAGES, selectAnotherPdf() {} })));
  assert.match(html, /role="alert"/);
  assert.ok(html.includes(BROKER_STATEMENT_MESSAGES.TOSS_INCOMPLETE));
  assert.doesNotMatch(html, /매매 복기로 가져오기/);
});

// Render the real component and invoke its handlers in the existing isolated VM.
function brokerConfirmationHarness(trades) {
  const source = readFileSync(new URL('../src/components/BrokerImport.jsx', import.meta.url), 'utf8');
  const fileAst = ts.createSourceFile('BrokerImport.jsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.JSX);
  assert.deepEqual(fileAst.parseDiagnostics, []);
  const component = fileAst.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === 'BrokerImport');
  let state = { status: 'ready', statementStatus: BROKER_STATEMENT_STATUS.READY, fileName: 'synthetic.pdf',
    trades, selectedIds: new Set(), tradeStates: Object.fromEntries(trades.map(row => [row.id, createTradeTimeState(row.tradeTime)])),
    pageCount: 1, textItemCount: 10, message: '' };
  const transferred = [];
  const context = syntheticContext({ React, useRef: () => ({ current: null }),
    useState: () => [state, value => { state = typeof value === 'function' ? value(state) : value; }],
    Check: () => null, FileText: () => null, ShieldCheck: () => null,
    BROKER_STATEMENT_STATUS, BROKER_STATEMENT_MESSAGES, REVIEW_TIME_VALIDATION_MESSAGES,
    brokerReviewTradeIssue, createTradeTimeState, formatTradeDateTime, formatTradeNumber,
    setTradeTimeUnknownState, sortTradesByDateDesc, tradeSideLabel, updateTradeTimeState, validateTradeTimesForReview,
  });
  const Component = expressionInContext(component.getText(fileAst).replace(/^export default /, ''), context);
  return { get state() { return state; }, transferred,
    render: (embedded = true) => Component({ embedded, onImportToJournal: rows => transferred.push(rows) }) };
}

function brokerElements(node, predicate) {
  if (Array.isArray(node)) return node.flatMap(child => brokerElements(child, predicate));
  if (!React.isValidElement(node)) return [];
  return [...(predicate(node) ? [node] : []), ...brokerElements(node.props.children, predicate)];
}

const confirmationRow = (view, id) => brokerElements(view, node => node.type === 'li' && node.key === id)[0];
const confirmationChecks = view => brokerElements(view, node => node.type === 'input' && node.props.type === 'checkbox');
const transferButton = view => brokerElements(view, node => node.type === 'button' && node.props.children === '매매 복기로 가져오기')[0];
const confirmationTrade = (id, extra = {}) => ({ id, tradeDate: '2026-09-02', stockName: '합성종목', symbol: '005930',
  side: 'buy', price: 70000, quantity: 1, fee: 0, tax: 0, tradeTime: null, sourceIndex: Number(id.slice(-1)), ...extra });

test('broker confirmation re-sorts manual times while retaining row identity and selection', () => {
  const input = [confirmationTrade('pdf-trade-0', { tradeDate: '2026-09-03' }),
    confirmationTrade('pdf-trade-1', { tradeTime: '09:30' }), confirmationTrade('pdf-trade-2', { tradeTime: '14:00' }),
    confirmationTrade('pdf-trade-3')];
  const h = brokerConfirmationHarness(input);
  const order = () => brokerElements(h.render(), node => node.type === 'li').map(node => node.key);
  const select = id => confirmationChecks(confirmationRow(h.render(), id))[0].props.onChange();
  select('pdf-trade-1');
  select('pdf-trade-3');
  assert.deepEqual(order(), ['pdf-trade-0', 'pdf-trade-2', 'pdf-trade-1', 'pdf-trade-3']);
  const time = id => brokerElements(confirmationRow(h.render(), id), node => node.type === 'input' && node.props.type === 'time')[0];
  time('pdf-trade-1').props.onChange({ target: { value: '16:00' } });
  assert.deepEqual(order(), ['pdf-trade-0', 'pdf-trade-1', 'pdf-trade-2', 'pdf-trade-3']);
  assert.equal(time('pdf-trade-3').props.disabled, false, 'optional blank time stays editable');
  time('pdf-trade-3').props.onChange({ target: { value: '16:00' } });
  assert.deepEqual(order(), ['pdf-trade-0', 'pdf-trade-1', 'pdf-trade-3', 'pdf-trade-2']);
  time('pdf-trade-1').props.onChange({ target: { value: '' } });
  assert.deepEqual(order(), ['pdf-trade-0', 'pdf-trade-3', 'pdf-trade-2', 'pdf-trade-1']);
  assert.equal(h.state.tradeStates['pdf-trade-1'].timeUnknown, true);
  assert.equal(h.state.tradeStates['pdf-trade-1'].tradeTime, null);
  assert.equal(time('pdf-trade-1').props.disabled, false);
  assert.deepEqual(order(), ['pdf-trade-0', 'pdf-trade-3', 'pdf-trade-2', 'pdf-trade-1']);
  assert.deepEqual([...h.state.selectedIds].sort(), ['pdf-trade-1', 'pdf-trade-3']);
  assert.equal(confirmationChecks(confirmationRow(h.render(), 'pdf-trade-1'))[0].props.checked, true);
  assert.deepEqual(input.map(row => [row.id, row.tradeTime]), [
    ['pdf-trade-0', null], ['pdf-trade-1', '09:30'], ['pdf-trade-2', '14:00'], ['pdf-trade-3', null],
  ]);
  assert.equal(transferButton(h.render()).props.disabled, false);
  transferButton(h.render()).props.onClick();
  assert.deepEqual(Array.from(h.transferred[0], row => row.id), ['pdf-trade-3', 'pdf-trade-1']);
  assert.equal(new Set(h.transferred[0].map(row => row.id)).size, 2);
});

test('broker confirmation explains blocked costs and instruments and permits deselecting them', () => {
  const h = brokerConfirmationHarness([confirmationTrade('pdf-trade-1'),
    confirmationTrade('pdf-trade-2', { fee: null }), confirmationTrade('pdf-trade-3', { fee: 69, tax: null }),
    confirmationTrade('pdf-trade-4', { symbol: '' }), confirmationTrade('pdf-trade-5', { fee: null, tax: null })]);
  const html = renderToStaticMarkup(h.render());
  assert.match(html, /수수료 정보가 없어 복기를 준비할 수 없습니다/);
  assert.match(html, /세금 정보가 없어 복기를 준비할 수 없습니다/);
  assert.match(html, /수수료와 세금 정보가 없어 복기를 준비할 수 없습니다/);
  assert.match(html, /종목명과 6자리 종목코드 확인/);
  assert.match(renderToStaticMarkup(confirmationRow(h.render(), 'pdf-trade-3')), /수수료 69원 · 세금 정보 없음/);
  assert.match(html, /수수료 정보 없음/);
  assert.match(html, /종목·가격·수량·비용 수정 및 메모 입력은 아직 지원하지 않습니다/);
  assert.match(journalSource, /가져온 거래의 매매 메모 입력은 현재 지원하지 않습니다/);
  assert.doesNotMatch(journalSource, /매매 이유와 판단은 매매복기에서 작성할 수 있습니다/);
  for (const embedded of [true, false]) {
    const support = renderToStaticMarkup(h.render(embedded));
    assert.match(support, /토스증권 국내주식 거래내역서를 지원/);
    assert.match(support, /그 외 단순 텍스트 형식은 제한적으로/);
    assert.match(support, /해외·환율 거래/);
    assert.match(support, /암호화 PDF/);
    assert.match(support, /PDF 원본은 스톡보다 서버로 전송되거나 저장되지 않습니다/);
    assert.doesNotMatch(support, /지원 예정/);
  }
  confirmationChecks(h.render())[0].props.onChange();
  assert.equal(h.state.selectedIds.size, 5);
  assert.equal(transferButton(h.render()).props.disabled, true);
  assert.match(renderToStaticMarkup(h.render()), /해당 거래를 선택 해제/);
  transferButton(h.render()).props.onClick();
  assert.equal(h.transferred.length, 0, 'handler must also fail closed without relying on disabled');
  for (const id of ['pdf-trade-2', 'pdf-trade-3', 'pdf-trade-4', 'pdf-trade-5']) {
    confirmationChecks(confirmationRow(h.render(), id))[0].props.onChange();
  }
  assert.equal(transferButton(h.render()).props.disabled, false);
  transferButton(h.render()).props.onClick();
  assert.deepEqual(Array.from(h.transferred[0], row => row.id), ['pdf-trade-1']);
  assert.equal(prepareBrokerReviewInput(h.transferred[0]).groups[0].trades.length, 1);
  assert.equal(h.state.trades[1].fee, null);
  assert.equal(h.state.trades[2].tax, null);
});

test('broker confirmation optional times stay editable and blank across dates without unknown controls', () => {
  const h = brokerConfirmationHarness([confirmationTrade('pdf-trade-1', { tradeDate: '2026-08-28' }),
    confirmationTrade('pdf-trade-2', { tradeDate: '2026-08-29', side: 'sell' })]);
  confirmationChecks(h.render())[0].props.onChange();
  const times = () => brokerElements(h.render(), node => node.type === 'input' && node.props.type === 'time');
  assert.equal(times().length, 2);
  assert.ok(times().every(node => !node.props.disabled && !node.props.required));
  assert.equal(confirmationChecks(h.render()).length, 3, 'only select-all and two row selections');
  assert.doesNotMatch(renderToStaticMarkup(h.render()), /시간을 모름/);
  assert.equal(transferButton(h.render()).props.disabled, false);
  times()[0].props.onChange({ target: { value: '12:34' } });
  assert.deepEqual({ ...h.state.tradeStates['pdf-trade-2'] }, { tradeTime: '12:34', timeUnknown: false });
  times()[0].props.onChange({ target: { value: '' } });
  assert.deepEqual({ ...h.state.tradeStates['pdf-trade-2'] }, { tradeTime: null, timeUnknown: true });
  assert.equal(transferButton(h.render()).props.disabled, false);
  transferButton(h.render()).props.onClick();
  const prepared = prepareBrokerReviewInput(h.transferred[0]);
  assert.equal(prepared.groups[0].trades.length, 2);
  assert.ok(prepared.groups[0].previewTrades.every(row => row.tradeTime === null && row.timeUnknown));
});

test('broker confirmation preserves mixed-side required times and select-all behavior', () => {
  const h = brokerConfirmationHarness([confirmationTrade('pdf-trade-1'), confirmationTrade('pdf-trade-2', { side: 'sell' })]);
  confirmationChecks(h.render())[0].props.onChange();
  assert.equal(h.state.selectedIds.size, 2);
  assert.equal(transferButton(h.render()).props.disabled, true);
  assert.match(renderToStaticMarkup(h.render()), /체결시간이 필요합니다/);
  transferButton(h.render()).props.onClick();
  assert.equal(h.transferred.length, 0);
  confirmationChecks(confirmationRow(h.render(), 'pdf-trade-2'))[0].props.onChange();
  assert.equal(transferButton(h.render()).props.disabled, false, 'BUY-only time is optional');
  confirmationChecks(confirmationRow(h.render(), 'pdf-trade-2'))[0].props.onChange();
  for (const [id, value] of [['pdf-trade-1', '09:30'], ['pdf-trade-2', '14:00']]) {
    confirmationChecks(confirmationRow(h.render(), id))[1].props.onChange({ target: { checked: false } });
    brokerElements(confirmationRow(h.render(), id), node => node.type === 'input' && node.props.type === 'time')[0]
      .props.onChange({ target: { value } });
  }
  assert.equal(transferButton(h.render()).props.disabled, false);
  assert.equal(prepareBrokerReviewInput(h.state.trades.map(row => ({ ...row, ...h.state.tradeStates[row.id] }))).groups.length, 1);
  transferButton(h.render()).props.onClick();
  assert.equal(h.transferred[0].length, 2);
  confirmationChecks(h.render())[0].props.onChange();
  assert.equal(h.state.selectedIds.size, 0);
  assert.equal(transferButton(h.render()).props.disabled, true);
});

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
    return React.createElement(ReviewBodyRenderer, props);
  }
  const view = compileProduction(`const view = ${liveExpression};`, {
    React, aiReview, aiLoading: false, aiChartSource: aiReviewChartSource(aiReview),
    basicReviewInput, aiReviewSource: null, adLoading: false, aiConsentAccepted: true,
    deepenBasicReview: () => assert.fail('rendering must not execute advanced review'),
    reviewAccessText: () => '', CanonicalReviewRenderer, ReviewBodyRenderer: ObserveCanonical,
  }, 'view');
  const html = renderToStaticMarkup(view);
  const body = observed.find(props => props.expectedSurface === undefined);
  assert.ok(body, 'actual production JSX must use the canonical body renderer');
  const bodyHtml = renderToStaticMarkup(React.createElement(ReviewBodyRenderer, body));
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
  assert.match(journalSource, /startAdvancedReview = \(nextTrades = selectedReviewTrades/);
  assert.match(journalSource, /loadAiReview\(nextTrades, 'advanced', options\)/);
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
  assert.ok(selectedReviewExpression);
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

async function verifyImportedPreparation() {
  assert.match(journalSource, /setShowCurrentReviewDetails\(false\)/);
  assert.match(journalSource, /showCurrentReviewDetails && <section className="journal-panel">/);
  assert.ok(prepareButtonExpression);
  const rows = [
    { id: 'pdf-trade-1', tradeDate: '2026-09-02', symbol: '032940', stockName: '원익', side: 'buy', price: 7830, quantity: 1, fee: 1, tax: 0, tradeTime: null, timeUnknown: true },
    { id: 'pdf-trade-2', tradeDate: '2026-09-02', symbol: '032940', stockName: '원익', side: 'sell', price: 7710, quantity: 1, fee: 1, tax: 15, tradeTime: null, timeUnknown: true },
  ];
  const savedTrades = [{ id: 41, name: 'Saved trade', ticker: '005930' }];
  const state = { prepared: null, savedTrades, details: true };
  const context = syntheticContext({ React, importedTrades: rows, loading: false, aiLoading: false, adLoading: false, prepareBrokerReviewInput,
    setPreparedImportedReview: value => { state.prepared = value; },
    setSelectedReviewGroupKey: value => { state.key = value; },
    setShowCurrentReviewDetails: value => { state.details = value; },
    setReview: value => { state.review = value; }, setAiReview: value => { state.aiReview = value; },
    setMessage: value => { state.message = value; }, onClearImportedTrades: () => { state.cleared = true; },
    setTrades: () => assert.fail('preparation must not replace saved trades'),
    setReviewTargetQuery: () => {}, setReviewTargetFrom: () => {}, setReviewTargetTo: () => {},
    setChartReview: () => {}, setActiveChartTicker: () => {},
  });
  // Preparation may call only the pure adapter, local setters and preview cleanup.
  // Reject any newly introduced API/storage/AI call without providing those globals.
  const allowedCalls = new Set(['prepareBrokerReviewInput', 'setPreparedImportedReview', 'setSelectedReviewGroupKey',
    'setReviewTargetQuery', 'setReviewTargetFrom', 'setReviewTargetTo', 'setReview', 'setAiReview', 'setChartReview',
    'setActiveChartTicker', 'setShowCurrentReviewDetails', 'onClearImportedTrades', 'setMessage']);
  function checkPreparationCalls(node) {
    if (ts.isCallExpression(node)) assert.ok(allowedCalls.has(node.expression.getText(ast)), node.expression.getText(ast));
    ts.forEachChild(node, checkPreparationCalls);
  }
  checkPreparationCalls(initializers.get('prepareImportedTrades'));
  context.prepareImportedTrades = handlerInContext('prepareImportedTrades', context);
  function button() {
    context.importedTimeValidation = validateTradeTimesForReview(context.importedTrades);
    return expressionInContext(prepareButtonExpression, context);
  }
  let view = button();
  assert.equal(view.props.disabled, true);
  view.props.onClick(); // Even a stale/programmatic click revalidates, with zero effects.
  assert.equal(state.prepared, null);
  assert.equal(state.cleared, undefined);
  context.importedTrades = rows.map((row, index) => ({ ...row, tradeTime: index ? '14:10' : '09:30', timeUnknown: false }));
  const confirmedCosts = context.importedTrades;
  for (const field of ['fee', 'tax']) {
    context.importedTrades = confirmedCosts.map(row => ({ ...row, [field]: null }));
    button().props.onClick();
    assert.equal(state.prepared, null, 'unknown costs cannot publish prepared input');
    assert.equal(state.cleared, undefined, 'unknown costs leave the pending selection available');
    assert.equal(state.message, `${field === 'fee' ? '수수료' : '세금'} 정보가 없어 복기를 준비할 수 없습니다.`);
    assert.ok(context.importedTrades.every(row => row[field] === null));
  }
  context.importedTrades = confirmedCosts;
  view = button();
  assert.equal(view.props.disabled, false);
  assert.ok(renderToStaticMarkup(view).includes('선택한 거래로 복기 준비'));
  view.props.onClick();
  assert.equal(state.details, false);
  assert.equal(state.aiReview, null);
  assert.equal(state.review, null);
  assert.equal(state.cleared, true);
  assert.strictEqual(state.savedTrades, savedTrades);
  assert.equal(state.key, 'broker:032940');
  const selected = reviewTradesForGroup(state.prepared.groups, state.key);
  assert.equal(selected.length, 2);
  assert.ok(selected.every(row => !('id' in row) && !('previewId' in row) && !('timeUnknown' in row)));

  // Run the unchanged actual AI handler with prepared input: only explicit execution
  // may call AI, retaining consent, display support and the normal entitlement path.
  for (const type of ['basic', 'advanced']) {
    const requests = [];
    const response = approvedResponse(vectors.valid.find(value => value.id === 'normal_bold').document, type);
    const io = syntheticContext({ trades: savedTrades, aiReviewType: type, aiConsentAccepted: true,
      apiBase: 'https://synthetic.invalid', authHeaders: { Authorization: 'Bearer synthetic' }, authSession: null,
      aiReviewInFlightRef: { current: false }, basicReviewFocusIndexRef: { current: 0 }, BASIC_REVIEW_FOCUSES: ['balanced'],
      captureReviewInput, aiReviewSourceRef: { current: null },
      setAiReviewSource: () => {},
      DEV_TOOLS_ENABLED: false, DEV_ACCESS_PLAN: 'free', DEV_AD_REWARD_TOKEN: '', DEV_ENTITLEMENT_TOKEN: '',
      buildAiReviewIdempotencyKey, aiReviewChartSource, reviewDisplayHeaders, reviewDisplayFailureMessage,
      setAiReview: context.setAiReview, setReview: context.setReview, setMessage: context.setMessage,
      setShowCurrentReviewDetails: context.setShowCurrentReviewDetails, setActiveChartTicker: () => {},
      setAiLoading: () => {}, setEntitlements: () => {}, loadReviewHistory: async () => {}, loadDataSummary: async () => {},
      axios: { async post(url, payload, config) { requests.push({ url, payload, config });
        return { data: url.endsWith('/ai-review-once') ? response : {} }; } },
    });
    io.loadReviewContextForTrades = handlerInContext('loadReviewContextForTrades', io);
    const load = handlerInContext('loadAiReview', io);
    await load(selected, type, { targetTradeId: state.prepared.groups[0].targetTradeId });
    assert.deepEqual(requests.map(value => value.url.split('/').at(-1)), ['ai-review-once', 'review-once']);
    assert.deepEqual(requests[0].payload.trades, selected);
    assert.deepEqual(requests[0].payload.trades.map(row => [row.fee, row.tax]), [[1, 0], [1, 15]]);
    assert.equal(requests[0].payload.target_trade_id, null);
    assert.equal(requests[0].payload.review_type, type);
    assert.deepEqual(requests[0].config.headers, reviewDisplayHeaders({ ...io.authHeaders,
      'X-Idempotency-Key': requests[0].config.headers['X-Idempotency-Key'] }));
    assert.strictEqual(state.aiReview.display_snapshot, response.display_snapshot);
  }
  // Switching to direct input removes only the import overlay; saved rows survive.
  context.journalInputMode = 'broker';
  context.preparedImportedReview = state.prepared;
  context.setJournalInputMode = value => { state.mode = value; };
  const direct = expressionInContext(directInputExpression, context);
  direct.props.onClick();
  assert.equal(state.mode, 'direct');
  assert.equal(state.prepared, null);
  assert.strictEqual(state.savedTrades, savedTrades);
}

test('saved journal entry does not reveal stock details until a review is selected or completed', async () => {
  try {
    await verifyImportedPreparation();
  } catch (error) {
    // The official reporter keeps case/status only; preserve the original stack in stderr.
    console.error(error?.stack || String(error));
    throw error;
  }
});

function verifyInputModeSelection() {
  for (const expression of [directInputExpression, brokerInputExpression, selectedReviewExpression, selectionExpression]) {
    assert.ok(expression);
  }
  const pending = [
    { id: 'pdf-trade-1', tradeDate: '2026-09-02', symbol: '032940', stockName: 'Synthetic import', side: 'buy', price: 7830, quantity: 1, fee: 1, tax: 0, tradeTime: null, timeUnknown: true },
    { id: 'pdf-trade-2', tradeDate: '2026-09-02', symbol: '032940', stockName: 'Synthetic import', side: 'sell', price: 7710, quantity: 1, fee: 1, tax: 15, tradeTime: null, timeUnknown: true },
  ];
  const saved = [
    { id: 41, trade_date: '2026-09-01T09:30', ticker: '005930', name: 'Synthetic saved', side: 'buy', price: 10000, quantity: 1 },
    { id: 42, trade_date: '2026-09-01T14:10', ticker: '005930', name: 'Synthetic saved', side: 'sell', price: 10100, quantity: 1 },
  ];
  const draft = { ticker: '000660', quantity: '2', memo: 'Unsaved direct input' };
  const context = syntheticContext({ React, importedTrades: pending, trades: saved, form: draft,
    journalInputMode: 'broker', preparedImportedReview: null, selectedReviewGroupKey: '',
    loading: false, aiLoading: false, adLoading: false, aiConsentAccepted: true, aiReviewType: 'basic',
    buildReviewTradeGroups, reviewTradesForGroup, prepareBrokerReviewInput, validateTradeTimesForReview,
    useMemo: compute => compute(),
    setTrades: () => assert.fail('mode switching must not replace saved trades'),
    setForm: () => assert.fail('mode switching must not replace the direct-input draft'),
    setReviewTargetQuery: () => {}, setReviewTargetFrom: () => {}, setReviewTargetTo: () => {},
    setChartReview: () => {}, setActiveChartTicker: () => {},
  });
  context.setJournalInputMode = value => { context.journalInputMode = value; };
  context.setPreparedImportedReview = value => { context.preparedImportedReview = value; };
  context.setSelectedReviewGroupKey = value => { context.selectedReviewGroupKey = value; };
  context.setShowCurrentReviewDetails = value => { context.details = value; };
  context.setReview = value => { context.review = value; };
  context.setAiReview = value => { context.aiReview = value; };
  context.setMessage = value => { context.message = value; };
  context.setAiReviewType = value => { context.aiReviewType = value; };
  context.rewardedBasicNeedsFreeUsage = false;
  context.mobileAdStatus = { native: false };
  context.handleRewardedAdBasicReview = () => assert.fail('selection must not start ads');
  context.onClearImportedTrades = () => { context.importedTrades = []; };
  context.prepareImportedTrades = handlerInContext('prepareImportedTrades', context);
  context.chooseReviewGroup = handlerInContext('chooseReviewGroup', context);
  context.startAdvancedReview = handlerInContext('startAdvancedReview', context);
  context.startSelectedReview = handlerInContext('startSelectedReview', context);
  function recalculateSelection() {
    for (const name of ['reviewTradeGroups', 'selectedReviewGroup', 'selectedReviewTrades', 'importedTimeValidation']) {
      context[name] = expressionInContext(initializers.get(name).getText(ast), context);
    }
  }
  function expectActionsDisabled(disabled) {
    assert.equal(expressionInContext(selectedReviewExpression, context).props.disabled, disabled);
    const selection = expressionInContext(selectionExpression, context);
    if (disabled) assert.equal(selection, false, 'no depth selection before trade input is ready');
    else assert.ok(renderToStaticMarkup(selection).includes('판단 과정까지 깊게 분석'));
  }
  function selectSaved() {
    recalculateSelection();
    context.chooseReviewGroup(context.reviewTradeGroups.find(group => group.ticker === '005930').key);
    recalculateSelection();
    assert.deepEqual(context.selectedReviewTrades, saved);
    assert.equal(context.selectedReviewGroup.targetTradeId, 42);
    expectActionsDisabled(false);
  }
  function assertDirectDataPreserved() {
    assert.strictEqual(context.trades, saved);
    assert.strictEqual(context.form, draft);
    assert.equal(context.form.memo, 'Unsaved direct input');
  }

  // Exact Major regression: selected PDF rows are still pending when switching modes.
  recalculateSelection();
  assert.equal(context.selectedReviewTrades.length, 0);
  expectActionsDisabled(true);
  assert.equal(expressionInContext(prepareButtonExpression, context).props.disabled, true);
  expressionInContext(directInputExpression, context).props.onClick();
  assert.equal(context.journalInputMode, 'direct');
  assert.strictEqual(context.importedTrades, pending);
  selectSaved();
  assertDirectDataPreserved();

  // Returning to broker preserves the same rows and blocks review until preparation.
  expressionInContext(brokerInputExpression, context).props.onClick();
  recalculateSelection();
  assert.equal(context.journalInputMode, 'broker');
  assert.strictEqual(context.importedTrades, pending);
  assert.equal(context.selectedReviewTrades.length, 0);
  expectActionsDisabled(true);
  const blocked = expressionInContext(prepareButtonExpression, context);
  assert.equal(blocked.props.disabled, true);
  blocked.props.onClick(); // Handler also refuses a stale/programmatic invalid click.
  assert.equal(context.preparedImportedReview, null);
  assert.strictEqual(context.importedTrades, pending);
  assertDirectDataPreserved();

  // Prepared input still selects import rows, then direct input restores saved groups.
  context.importedTrades = pending.map((row, index) => ({ ...row, tradeTime: index ? '14:10' : '09:30', timeUnknown: false }));
  recalculateSelection();
  const ready = expressionInContext(prepareButtonExpression, context);
  assert.equal(ready.props.disabled, false);
  ready.props.onClick();
  recalculateSelection();
  assert.equal(context.selectedReviewGroup.key, 'broker:032940');
  assert.equal(context.selectedReviewGroup.targetTradeId, null);
  assert.equal(context.selectedReviewTrades.length, 2);
  assert.ok(context.selectedReviewTrades.every(row => !('id' in row) && !('previewId' in row)));
  expectActionsDisabled(false);
  expressionInContext(directInputExpression, context).props.onClick();
  assert.equal(context.preparedImportedReview, null);
  selectSaved();
  assertDirectDataPreserved();

  // Existing direct-only users have no pending/prepared overlay.
  context.selectedReviewGroupKey = '';
  recalculateSelection();
  expectActionsDisabled(true);
  assert.equal(context.importedTrades.length, 0);
  selectSaved();
  assertDirectDataPreserved();
}

test('pending PDF selection blocks review only in broker mode and survives direct input round trips', () => {
  try {
    verifyInputModeSelection();
  } catch (error) {
    console.error(error?.stack || String(error));
    throw error;
  }
});

function reviewSelectionHarness(rows, targetTradeId = 42) {
  const requests = [];
  const jobs = [];
  const response = approvedResponse(vectors.valid.find(value => value.id === 'normal_bold').document);
  const context = syntheticContext({ React, trades: rows, selectedReviewTrades: rows,
    selectedReviewGroup: { targetTradeId }, selectedReviewGroupKey: 'unchanged-group',
    form: { memo: 'unsaved draft' }, aiReviewType: 'basic', aiConsentAccepted: true,
    aiLoading: false, adLoading: false, entitlements: { advanced: { signup_remaining: 1 } },
    apiBase: 'https://synthetic.invalid', authHeaders: {}, authSession: null,
    aiReviewInFlightRef: { current: false }, basicReviewFocusIndexRef: { current: 0 }, BASIC_REVIEW_FOCUSES: ['balanced'],
    captureReviewInput, basicReviewInput, aiReviewSourceRef: { current: null },
    aiReviewSource: null,
    CanonicalReviewRenderer, ReviewBodyRenderer, reviewAccessText: () => '',
    DEV_TOOLS_ENABLED: false, DEV_ACCESS_PLAN: 'free', DEV_AD_REWARD_TOKEN: '', DEV_ENTITLEMENT_TOKEN: '',
    buildAiReviewIdempotencyKey, aiReviewChartSource, reviewDisplayHeaders, reviewDisplayFailureMessage,
    rewardedBasicNeedsFreeUsage: false, mobileAdStatus: { native: false },
    handleRewardedAdBasicReview: () => assert.fail('selection/normal execution must not start advertising'),
    loadReviewHistory: async () => {}, loadDataSummary: async () => {},
    loadEntitlements: async () => { context.entitlementRefreshes = (context.entitlementRefreshes || 0) + 1; },
    setActiveChartTicker: () => {},
    axios: { async post(url, payload, config) {
      requests.push({ url, payload, config });
      if (context.synthetic402 && url.endsWith('/ai-review-once')) throw { response: { status: 402 } };
      return { data: url.endsWith('/ai-review-once') ? { ...response, review_type: payload.review_type } : {} };
    } },
  });
  for (const [setter, field] of [['setAiReviewType', 'aiReviewType'], ['setAiReview', 'aiReview'],
    ['setAiReviewSource', 'aiReviewSource'],
    ['setReview', 'review'], ['setMessage', 'message'], ['setAiLoading', 'aiLoading'],
    ['setEntitlements', 'entitlements'], ['setShowCurrentReviewDetails', 'details'], ['setReviewAccessDialog', 'dialog']]) {
    context[setter] = value => { context[field] = value; };
  }
  context.loadReviewContextForTrades = handlerInContext('loadReviewContextForTrades', context);
  const realLoad = handlerInContext('loadAiReview', context);
  context.loadAiReview = (...args) => { const job = realLoad(...args); jobs.push(job); return job; };
  context.startAdvancedReview = handlerInContext('startAdvancedReview', context);
  context.startSelectedReview = handlerInContext('startSelectedReview', context);
  context.deepenBasicReview = handlerInContext('deepenBasicReview', context);
  return { context, requests, jobs,
    selection: () => expressionInContext(selectionExpression, context),
    execution: () => expressionInContext(selectedReviewExpression, context),
    deepen: () => expressionInContext(deepenExpression, context),
    result: () => {
      context.aiChartSource = aiReviewChartSource(context.aiReview);
      return renderToStaticMarkup(expressionInContext(liveExpression, context));
    },
    choose: type => expressionInContext(type === 'basic' ? basicChoiceExpression : advancedChoiceExpression, context).props.onChange(),
  };
}

test('review depth cards appear only after direct selection or prepared broker input and selection preserves data', () => {
  assert.ok(selectionExpression && basicChoiceExpression && advancedChoiceExpression);
  const direct = [{ id: 42, trade_date: '2026-09-01T14:10', ticker: '005930', name: 'Synthetic', side: 'sell', price: 10100, quantity: 1 }];
  const imported = prepareBrokerReviewInput([
    { id: 'pdf-trade-1', tradeDate: '2026-09-02', symbol: '032940', stockName: 'Synthetic', side: 'buy', price: 7830, quantity: 1, fee: 1, tax: 0, tradeTime: null, timeUnknown: true },
  ]).groups[0].trades;
  let directHtml;
  for (const rows of [direct, imported]) {
    const harness = reviewSelectionHarness(rows, rows === direct ? 42 : null);
    const { context } = harness;
    const before = JSON.stringify(rows);
    const draft = context.form;
    const group = context.selectedReviewGroup;
    context.selectedReviewTrades = [];
    assert.equal(harness.selection(), false);
    assert.equal(harness.execution().props.disabled, true);
    context.selectedReviewTrades = rows;
    const basicHtml = renderToStaticMarkup(harness.selection());
    for (const text of ['빠르게 핵심만 확인', '판단 과정까지 깊게 분석', '잘한 점', '핵심 개선점', '다음 매매 행동',
      '매매 지식', '진입', '리스크', '매도 판단', '상세 근거', '플레이북', '복기 질문', '일반복기 실행']) assert.ok(basicHtml.includes(text), text);
    if (rows === direct) directHtml = basicHtml;
    else assert.equal(basicHtml, directHtml, 'both input sources converge on the identical production selection JSX');
    for (const type of ['advanced', 'basic']) {
      harness.choose(type);
      assert.equal(context.aiReviewType, type);
      const html = renderToStaticMarkup(harness.selection());
      assert.ok(html.includes(`${type === 'basic' ? '일반복기' : '심화복기'} 실행`));
      assert.equal(expressionInContext(basicChoiceExpression, context).props.checked, type === 'basic');
      assert.equal(expressionInContext(advancedChoiceExpression, context).props.checked, type === 'advanced');
      assert.strictEqual(context.selectedReviewTrades, rows);
      assert.strictEqual(context.selectedReviewGroup, group);
      assert.strictEqual(context.form, draft);
      assert.equal(context.selectedReviewGroupKey, 'unchanged-group');
      assert.equal(JSON.stringify(rows), before);
      assert.deepEqual(harness.requests, []);
      assert.deepEqual(harness.jobs, []);
    }
  }
});

test('selected depth execution retains actual basic advanced API and canonical payload contracts for both input paths', async () => {
  const direct = [{ id: 42, trade_date: '2026-09-01T14:10', ticker: '005930', name: 'Synthetic', side: 'sell', price: 10100, quantity: 1 }];
  const prepared = prepareBrokerReviewInput([
    { id: 'pdf-trade-1', tradeDate: '2026-09-02', symbol: '032940', stockName: 'Synthetic', side: 'buy', price: 7830, quantity: 1, fee: 1, tax: 0, tradeTime: '09:30', timeUnknown: false },
    { id: 'pdf-trade-2', tradeDate: '2026-09-02', symbol: '032940', stockName: 'Synthetic', side: 'sell', price: 7710, quantity: 1, fee: 1, tax: 15, tradeTime: '14:10', timeUnknown: false },
  ]);
  for (const rows of [direct, prepared.groups[0].trades]) {
    for (const type of ['basic', 'advanced']) {
      const harness = reviewSelectionHarness(rows, rows === direct ? 42 : null);
      const before = JSON.stringify(rows);
      harness.choose(type);
      assert.equal(harness.requests.length, 0);
      assert.equal(harness.execution().props.disabled, false);
      harness.execution().props.onClick();
      await Promise.all(harness.jobs);
      assert.equal(harness.jobs.length, 1);
      assert.deepEqual(harness.requests.map(value => value.url.split('/').at(-1)), ['ai-review-once', 'review-once']);
      const request = harness.requests[0];
      assert.strictEqual(request.payload.trades, rows);
      assert.equal(request.payload.review_type, type);
      assert.equal(request.payload.target_trade_id, rows === direct ? 42 : null);
      assert.equal(request.payload.privacy_consent, true);
      assert.equal(request.payload.ad_reward_token, '');
      assert.deepEqual(request.config.headers, reviewDisplayHeaders({ 'X-Idempotency-Key': request.config.headers['X-Idempotency-Key'] }));
      assert.equal(JSON.stringify(rows), before);
      assert.ok(harness.context.aiReview.display_snapshot);
      assert.equal(harness.context.aiLoading, false);
    }
  }
});

test('depth selection never bypasses consent busy guards or existing advanced entitlement admission', async () => {
  const rows = [{ id: 42, trade_date: '2026-09-01', ticker: '005930', side: 'buy', price: 10000, quantity: 1 }];
  for (const type of ['basic', 'advanced']) {
    const harness = reviewSelectionHarness(rows);
    harness.context.aiConsentAccepted = false;
    harness.choose(type); // Consent gates execution, not understanding the two choices.
    assert.equal(harness.execution().props.disabled, true);
    harness.execution().props.onClick(); // A stale click must also be harmless.
    assert.deepEqual(harness.requests, []);
    assert.deepEqual(harness.jobs, []);
    harness.context.aiConsentAccepted = true;
    for (const field of ['aiLoading', 'adLoading']) {
      harness.context[field] = true;
      const fieldset = React.Children.toArray(harness.selection().props.children).find(child => child.type === 'fieldset');
      assert.equal(fieldset.props.disabled, true);
      assert.equal(harness.execution().props.disabled, true);
      harness.execution().props.onClick();
      assert.deepEqual(harness.requests, []);
      harness.context[field] = false;
    }
    assert.equal(harness.execution().props.disabled, false);
  }
  const blocked = reviewSelectionHarness(rows);
  blocked.context.entitlements = { advanced: { signup_remaining: 0 } };
  blocked.choose('advanced');
  assert.equal(blocked.context.dialog, undefined, 'choosing depth does not acquire or consume a pass');
  assert.equal(blocked.execution().props.disabled, false);
  blocked.execution().props.onClick();
  assert.equal(blocked.context.dialog, 'advanced');
  assert.deepEqual(blocked.requests, []);
  const unknown = reviewSelectionHarness(rows);
  unknown.context.entitlements = null;
  unknown.context.synthetic402 = true;
  unknown.choose('advanced');
  unknown.execution().props.onClick();
  await Promise.all(unknown.jobs);
  assert.equal(unknown.requests.length, 1, 'unknown entitlement is still decided by the existing server path');
  assert.equal(unknown.context.dialog, 'advanced');
  assert.equal(unknown.context.entitlementRefreshes, 1);
  assert.equal(unknown.context.aiLoading, false);
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
      captureReviewInput, aiReviewSourceRef: { current: null },
      setAiReviewSource: () => {},
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

test('live basic result deepens the exact direct or broker request without re-entry or AI-output input', async () => {
  assert.ok(deepenExpression);
  const direct = [{ id: 42, trade_date: '2026-09-01T14:10:05', ticker: '005930', name: 'Synthetic',
    side: 'sell', price: 10100, quantity: 1, fee: 3, tax: 4, memo: 'Original reason', source: 'manual' }];
  const imported = prepareBrokerReviewInput([
    { id: 'pdf-trade-1', tradeDate: '2026-09-02', symbol: '032940', stockName: 'Synthetic', side: 'buy', price: 7830, quantity: 1, fee: 1, tax: 0, tradeTime: '09:30', timeUnknown: false },
    { id: 'pdf-trade-2', tradeDate: '2026-09-02', symbol: '032940', stockName: 'Synthetic', side: 'sell', price: 7710, quantity: 1, fee: 1, tax: 15, tradeTime: '14:10', timeUnknown: false },
  ]).groups[0].trades;
  for (const rows of [direct, imported]) {
    const target = rows === direct ? 42 : null;
    const h = reviewSelectionHarness(rows, target);
    const { context } = h;
    const before = JSON.stringify(rows);
    const draft = context.form;
    const group = context.selectedReviewGroup;
    h.execution().props.onClick();
    await Promise.all(h.jobs);
    const originalResult = context.aiReview;
    const input = basicReviewInput(originalResult, context.aiReviewSourceRef.current);
    assert.equal(JSON.stringify(input.trades), before);
    assert.notStrictEqual(input.trades, rows);
    assert.ok(Object.isFrozen(input) && Object.isFrozen(input.trades) && input.trades.every(Object.isFrozen));
    context.aiReviewType = 'advanced'; // The result's type, not the choice card, controls the CTA.
    const callsBefore = h.requests.length;
    const html = h.result();
    assert.ok(html.includes('일반복기 결과') && html.includes('심화복기로 더 깊게 보기'));
    assert.equal(h.requests.length, callsBefore, 'rendering and choosing depth never call services');
    assert.equal(h.deepen().props.disabled, false);
    h.deepen().props.onClick();
    h.deepen().props.onClick(); // Rapid repeat does not acquire a second ticket/request.
    await Promise.all(h.jobs);
    const aiCalls = h.requests.filter(call => call.url.endsWith('/ai-review-once'));
    assert.equal(aiCalls.length, 2);
    assert.equal(aiCalls[1].payload.review_type, 'advanced');
    assert.equal(JSON.stringify(aiCalls[1].payload.trades), before);
    assert.equal(aiCalls[1].payload.target_trade_id, target);
    assert.strictEqual(aiCalls[1].payload.trades, input.trades);
    assert.equal(aiCalls[1].payload.privacy_consent, true);
    assert.equal(aiCalls[1].payload.ad_reward_token, '');
    assert.equal(aiCalls[1].payload.analysis_focus, '');
    assert.ok(aiCalls.every(call => call.config.headers['X-Review-Display-Contract'] === 'review-display.v1'));
    if (target === null) assert.ok(input.trades.every(row => !('id' in row) && !('previewId' in row)));
    else assert.equal(input.trades[0].id, 42);
    assert.strictEqual(context.selectedReviewTrades, rows);
    assert.strictEqual(context.selectedReviewGroup, group);
    assert.strictEqual(context.form, draft);
    assert.equal(context.selectedReviewGroupKey, 'unchanged-group');
    assert.equal(JSON.stringify(rows), before);
    assert.equal(context.aiReview.review_type, 'advanced');
    assert.notStrictEqual(context.aiReview, originalResult);
    const advancedHtml = h.result();
    assert.ok(advancedHtml.includes('심화복기 결과'));
    assert.ok(!advancedHtml.includes('일반복기 결과') && !advancedHtml.includes('심화복기로 더 깊게 보기'));
  }
});

test('basic result CTA fails closed on invalid canonical output missing source or a different response', () => {
  const rows = [{ id: 42, trade_date: '2026-09-01', ticker: '005930', name: 'Synthetic', side: 'buy', price: 10000, quantity: 1 }];
  const h = reviewSelectionHarness(rows);
  const good = approvedResponse(vectors.valid[0].document);
  const source = { review: good, input: captureReviewInput(rows, 42) };
  h.context.aiReview = good;
  h.context.aiReviewSourceRef.current = source;
  h.context.aiReviewSource = source;
  assert.ok(h.result().includes('심화복기로 더 깊게 보기'));
  for (const review of [
    { ...good, review_type: 'advanced' }, { ...good, review_type: 'general' },
    { ...good, status: 'error' }, { ...good, status: 'empty' }, { ...good, status: 'request_error' },
    { ...good, internal_status: 'rejected' }, { ...good, display_snapshot: null },
    { ...good, display_snapshot: { ...good.display_snapshot, canonical_text: 'UNAPPROVED' } },
    { ...good, chart_display_snapshot: { charts: [], chart_cards: [{ display: {} }] } },
  ]) {
    h.context.aiReview = review;
    h.context.aiReviewSourceRef.current = { ...source, review };
    h.context.aiReviewSource = h.context.aiReviewSourceRef.current;
    assert.equal(basicReviewInput(review, h.context.aiReviewSourceRef.current), null);
    assert.ok(!h.result().includes('심화복기로 더 깊게 보기'));
    h.context.deepenBasicReview(); // Stale/programmatic event must recheck admission.
  }
  h.context.aiReview = good;
  for (const invalidSource of [null, { ...source, input: null }, { ...source, review: { ...good } }]) {
    h.context.aiReviewSourceRef.current = invalidSource;
    h.context.aiReviewSource = invalidSource;
    assert.ok(!h.result().includes('심화복기로 더 깊게 보기'));
    h.context.deepenBasicReview();
  }
  assert.deepEqual(h.requests, []);
  assert.deepEqual(h.jobs, []);
});

test('basic to advanced CTA retains consent busy known-zero and unknown-wallet server 402 gates', async () => {
  const rows = [{ id: 42, trade_date: '2026-09-01', ticker: '005930', name: 'Synthetic', side: 'buy', price: 10000, quantity: 1 }];
  const h = reviewSelectionHarness(rows);
  h.execution().props.onClick();
  await Promise.all(h.jobs);
  const before = h.requests.length;
  for (const field of ['aiLoading', 'adLoading']) {
    h.context[field] = true;
    assert.equal(h.deepen().props.disabled, true);
    h.deepen().props.onClick();
    assert.equal(h.requests.length, before);
    h.context[field] = false;
  }
  h.context.aiConsentAccepted = false;
  assert.equal(h.deepen().props.disabled, true);
  h.deepen().props.onClick();
  assert.equal(h.requests.length, before);
  h.context.aiConsentAccepted = true;
  h.context.entitlements = { advanced: { signup_remaining: 0 } };
  const basicResult = h.context.aiReview;
  h.deepen().props.onClick();
  assert.equal(h.context.dialog, 'advanced');
  assert.strictEqual(h.context.aiReview, basicResult);
  assert.equal(h.requests.length, before);
  assert.equal(h.context.entitlements.advanced.signup_remaining, 0);
  h.context.entitlements = null;
  h.context.synthetic402 = true;
  h.deepen().props.onClick();
  await Promise.all(h.jobs);
  assert.equal(h.requests.length, before + 1);
  assert.equal(h.context.dialog, 'advanced');
  assert.equal(h.context.entitlementRefreshes, 1);
  assert.equal(h.context.aiLoading, false);
  assert.ok(!h.result().includes('심화복기로 더 깊게 보기'));
});

test('live basic original input remains exact despite pending request selection and trade mutations', async () => {
  const rows = Array.from({ length: 12 }, (_, index) => ({ id: index + 1, trade_date: '2026-09-01T09:30',
    ticker: '005930', name: 'Synthetic', side: 'buy', price: 10000 + index, quantity: 1 }));
  const h = reviewSelectionHarness(rows, 12);
  const before = JSON.stringify(rows);
  let resolve;
  const post = h.context.axios.post;
  h.context.axios.post = (url, payload, config) => url.endsWith('/ai-review-once') && payload.review_type === 'basic'
    ? new Promise(done => { resolve = done; }) : post(url, payload, config);
  h.execution().props.onClick();
  rows[0].price = 999999;
  h.context.selectedReviewTrades = [{ id: 99 }];
  h.context.selectedReviewGroup = { targetTradeId: 99 };
  resolve({ data: approvedResponse(vectors.valid[0].document) });
  await Promise.all(h.jobs);
  assert.ok(h.result().includes('심화복기로 더 깊게 보기'));
  h.deepen().props.onClick();
  await Promise.all(h.jobs);
  const advanced = h.requests.find(call => call.payload.review_type === 'advanced');
  assert.equal(JSON.stringify(advanced.payload.trades), before);
  assert.equal(advanced.payload.trades.length, 12, 'never truncate to the history ten-row snapshot');
  assert.equal(advanced.payload.target_trade_id, 12);
  assert.equal(h.context.selectedReviewGroup.targetTradeId, 99);
  assert.equal(h.context.selectedReviewTrades[0].id, 99);
});

test('account workspace reset invalidates live basic original input even after an old response completes', async () => {
  const rows = [{ id: 42, trade_date: '2026-09-01', ticker: '005930', name: 'Synthetic', side: 'buy', price: 10000, quantity: 1 }];
  const h = reviewSelectionHarness(rows);
  let resolve;
  h.context.axios.post = url => url.endsWith('/ai-review-once')
    ? new Promise(done => { resolve = done; }) : Promise.resolve({ data: {} });
  h.execution().props.onClick();
  assert.ok(h.context.aiReviewSourceRef.current.input);
  for (const setter of ['setPreparedImportedReview', 'setTrades', 'setChartReview', 'setSelectedReviewGroupKey',
    'setReviewTargetQuery', 'setReviewTargetFrom', 'setReviewTargetTo', 'setReviewHistory', 'setActiveReviewHistory', 'setJournalSubView']) {
    h.context[setter] = () => {};
  }
  handlerInContext('resetJournalWorkspace', h.context)();
  assert.equal(h.context.aiReviewSourceRef.current, null);
  resolve({ data: approvedResponse(vectors.valid[0].document) });
  await Promise.all(h.jobs);
  assert.equal(h.context.aiReviewSourceRef.current, null);
  assert.ok(!h.result().includes('심화복기로 더 깊게 보기'));
  h.context.deepenBasicReview();
  assert.deepEqual(h.requests, []);
});

test('original input capture preserves optional time and numeric identity without accepting preview ids', () => {
  const trade = { trade_date: '2026-09-01', ticker: '005930', name: 'Synthetic', side: 'buy', price: 10000, quantity: 1 };
  for (const rows of [[trade], [{ ...trade, id: null }], [{ ...trade, id: 42, trade_date: '2026-09-01T14:10:05', fee: 3.25, tax: 1.5, source: 'manual', memo: 'original' }]]) {
    const before = JSON.stringify(rows);
    const snapshot = captureReviewInput(rows, rows[0].id ?? null);
    assert.equal(JSON.stringify(snapshot.trades), before);
    assert.equal(snapshot.targetTradeId, rows[0].id ?? null);
  }
  for (const row of [{ ...trade, id: 'pdf-trade-1' }, { ...trade, id: '42' },
    { ...trade, previewId: 'pdf-trade-1' }, { ...trade, timeUnknown: true },
    { ...trade, price: NaN }, { ...trade, quantity: 0 }, { ...trade, side: 'unknown' }]) {
    assert.equal(captureReviewInput([row]), null);
  }
  assert.equal(captureReviewInput([]), null);
  assert.equal(captureReviewInput([trade], 'pdf-trade-1'), null);
  assert.equal(captureReviewInput([{ ...trade, id: 42 }], 99), null);
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
