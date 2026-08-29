import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import {
  BROKER_STATEMENT_MESSAGES,
  BROKER_STATEMENT_STATUS,
  createTradeTimeState,
  detectBrokerStatement,
  formatTradeDateTime,
  normalizeOptionalTradeTime,
  parseBrokerStatement,
  parseTradeCandidates,
  setTradeTimeUnknownState,
  sortTradesByDateDesc,
  updateTradeTimeState,
} from '../src/utils/brokerImport.js';

const componentSource = readFileSync(new URL('../src/components/BrokerImport.jsx', import.meta.url), 'utf8');
const journalSource = readFileSync(new URL('../src/components/TradingJournal.jsx', import.meta.url), 'utf8');
const extractorSource = readFileSync(new URL('../src/utils/pdfTextExtractor.js', import.meta.url), 'utf8');

test('keeps every clear candidate as an independent trade and sorts newest first', () => {
  const trades = parseTradeCandidates([
    '2026.08.27 09:17 삼성전자 005930 매수 20주 @ 72,400',
    '2026.08.27 14:32 삼성전자 005930 매도 74,800원 10주',
    '2026.08.27 10:30 삼성전자 005930 매수 10주 @ 71,000',
    '2026.08.27 삼성전자 005930 매수 70,000원 5주',
  ].join('\n'));

  assert.equal(trades.length, 4);
  assert.deepEqual(trades.map(trade => trade.tradeTime), ['14:32', '10:30', '09:17', null]);
  assert.deepEqual(trades.map(trade => trade.side), ['sell', 'buy', 'buy', 'buy']);
  assert.deepEqual(trades.map(trade => trade.quantity), [10, 10, 20, 5]);
  assert.equal(new Set(trades.map(trade => trade.id)).size, 4);
  assert.equal('sourceLine' in trades[0], false);
});

test('supports side-before-name rows without merging or inventing a time', () => {
  const trades = parseTradeCandidates('2026-08-26 매수 SK하이닉스 000660 250,000원 2주');

  assert.equal(trades.length, 1);
  assert.equal(trades[0].stockName, 'SK하이닉스');
  assert.equal(trades[0].symbol, '000660');
  assert.equal(trades[0].tradeTime, null);
  assert.equal(formatTradeDateTime(trades[0]), '2026.08.26');
});

test('rejects rows when price and quantity have no explicit meaning', () => {
  const trades = parseTradeCandidates('2026-08-25 삼성전자 매수 70000 10');

  assert.deepEqual(trades, []);
});

test('maps explicit quantity and price markers to the correct fields', () => {
  const quantityAtPrice = parseTradeCandidates('2026-08-27 삼성전자 매수 10주 @ 70,000');
  const priceThenQuantity = parseTradeCandidates('2026-08-27 삼성전자 매수 70,000원 10주');

  assert.equal(quantityAtPrice.length, 1);
  assert.equal(quantityAtPrice[0].quantity, 10);
  assert.equal(quantityAtPrice[0].price, 70000);
  assert.equal(priceThenQuantity.length, 1);
  assert.equal(priceThenQuantity[0].quantity, 10);
  assert.equal(priceThenQuantity[0].price, 70000);
});

test('classifies supported generic rows without guessing an unknown broker layout', () => {
  const parsed = parseBrokerStatement('2026-08-27 삼성전자 매수 10주 @ 70,000');

  assert.equal(parsed.status, BROKER_STATEMENT_STATUS.READY);
  assert.equal(parsed.trades.length, 1);
  assert.equal(parsed.trades[0].quantity, 10);
  assert.equal(parsed.trades[0].price, 70000);
});

test('rejects overseas or Toss statements before treating them as domestic trades', () => {
  const overseasText = '해외주식 거래내역 USD AAPL 매수 10주 @ 70,000';
  const tossText = '토스증권 국내주식 거래내역서';

  assert.deepEqual(detectBrokerStatement(overseasText), {
    broker: 'unknown',
    market: 'overseas',
    currency: 'foreign',
    hasTossMarker: false,
    hasOverseasMarker: true,
    hasDomesticMarker: false,
  });
  assert.equal(parseBrokerStatement(overseasText).status, BROKER_STATEMENT_STATUS.OVERSEAS_UNSUPPORTED);
  assert.deepEqual(parseBrokerStatement(overseasText).trades, []);
  assert.equal(parseBrokerStatement(tossText).status, BROKER_STATEMENT_STATUS.TOSS_DOMESTIC_SAMPLE_REQUIRED);
  assert.deepEqual(parseBrokerStatement(tossText).trades, []);
  assert.match(BROKER_STATEMENT_MESSAGES.OVERSEAS_UNSUPPORTED, /국내주식만 지원/);
  assert.match(BROKER_STATEMENT_MESSAGES.OVERSEAS_UNSUPPORTED, /해외주식은 추후 지원/);
});

test('keeps execution time optional and never invents it', () => {
  const trade = parseTradeCandidates('2026-08-27 삼성전자 매수 10주 @ 70,000')[0];

  assert.equal(trade.tradeTime, null);
  assert.equal(normalizeOptionalTradeTime('09:10'), '09:10');
  assert.equal(normalizeOptionalTradeTime('25:00'), null);
  assert.equal(normalizeOptionalTradeTime(''), null);
});

test('keeps timeUnknown and tradeTime independent for every selected trade', () => {
  const transition = (rows, id, update) => rows.map(row => (
    row.id === id ? { ...row, ...update(row) } : row
  ));

  let rows = [
    { id: 'buy-1', ...createTradeTimeState() },
    { id: 'buy-2', ...createTradeTimeState() },
    { id: 'sell-1', ...createTradeTimeState('14:10') },
  ];
  assert.deepEqual(rows[0], { id: 'buy-1', tradeTime: null, timeUnknown: true });
  assert.equal(rows[0].timeUnknown, true, 'time input starts disabled');

  rows = transition(rows, 'buy-1', row => setTradeTimeUnknownState(row, false));
  assert.deepEqual(rows[0], { id: 'buy-1', tradeTime: '', timeUnknown: false });
  assert.equal(rows[0].timeUnknown, false, 'time input becomes enabled after unchecking');

  rows = transition(rows, 'buy-1', row => updateTradeTimeState(row, '09:37'));
  assert.deepEqual(rows[0], { id: 'buy-1', tradeTime: '09:37', timeUnknown: false });

  rows = transition(rows, 'buy-1', row => setTradeTimeUnknownState(row, true));
  assert.deepEqual(rows[0], { id: 'buy-1', tradeTime: null, timeUnknown: true });
  assert.equal(rows[0].timeUnknown, true, 'time input is disabled again');

  rows = transition(rows, 'buy-1', row => setTradeTimeUnknownState(row, false));
  assert.deepEqual(rows[0], { id: 'buy-1', tradeTime: '', timeUnknown: false });
  assert.equal(rows[0].timeUnknown, false, 'time input can be enabled again');
  assert.deepEqual(rows[1], { id: 'buy-2', tradeTime: null, timeUnknown: true });
  assert.deepEqual(rows[2], { id: 'sell-1', tradeTime: '14:10', timeUnknown: false });

  assert.equal(componentSource.includes('disabled={timeUnknown}'), true);
  assert.equal(journalSource.includes('disabled={timeUnknown}'), true);
  assert.equal(componentSource.includes('const timeUnknown = !tradeTime'), false);
  assert.equal(journalSource.includes('const timeUnknown = !trade.tradeTime'), false);
});

test('rejects ambiguous rows that could carry customer or account information', () => {
  const trades = parseTradeCandidates([
    '2026-08-27 09:10 홍길동 계좌 123-45 삼성전자 005930 매수 70,000 10',
    '2026-08-27 09:10 홍길동 계좌 123-45 삼성전자 005930 매수 70,000원 10주',
  ].join('\n'));

  assert.deepEqual(trades, []);
});

test('does not merge identical repeated rows', () => {
  const trades = parseTradeCandidates([
    '2026-08-25 09:00 삼성전자 005930 매수 70,000원 10주',
    '2026-08-25 09:00 삼성전자 005930 매수 70,000원 10주',
  ].join('\n'));

  assert.equal(trades.length, 2);
  assert.deepEqual(trades.map(trade => trade.sourceIndex), [0, 1]);
});

test('rejects incomplete or invalid candidate rows', () => {
  const trades = parseTradeCandidates([
    '종목명 매수 70,000원 10주',
    '2026-02-30 삼성전자 005930 매수 70,000원 10주',
    '2026-08-25 삼성전자 005930 매도 70,000원',
  ].join('\n'));

  assert.deepEqual(trades, []);
});

test('sort helper preserves source order when date and time are equal', () => {
  const rows = [
    { tradeDate: '2026-08-27', tradeTime: '09:00', sourceIndex: 3 },
    { tradeDate: '2026-08-27', tradeTime: '09:00', sourceIndex: 1 },
  ];

  assert.deepEqual(sortTradesByDateDesc(rows).map(row => row.sourceIndex), [1, 3]);
});

test('local PDF flow has no client upload, API, or browser storage call', () => {
  assert.doesNotMatch(componentSource, /axios|fetch\s*\(|XMLHttpRequest|\/api\//i);
  assert.doesNotMatch(extractorSource, /axios|fetch\s*\(|XMLHttpRequest|\/api\//i);
  assert.doesNotMatch(componentSource, /localStorage|sessionStorage|indexedDB/i);
  assert.match(componentSource, /file\.arrayBuffer\(\)/);
  assert.match(componentSource, /기기에서만 처리됩니다/);
  assert.match(componentSource, /서버로 전송되거나 저장되지 않습니다/);
  assert.doesNotMatch(componentSource, /StockBoda backend|Render|OCR|\bDB\b/i);
  assert.match(componentSource, /onImportToJournal/);
  assert.match(componentSource, /시간을 모름/);
  assert.match(extractorSource, /getDocument\(\{[\s\S]*data,/);
  assert.match(extractorSource, /pdf\.worker\.min\.mjs\?url/);
});
