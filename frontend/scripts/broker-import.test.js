import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import {
  formatTradeDateTime,
  parseTradeCandidates,
  sortTradesByDateDesc,
} from '../src/utils/brokerImport.js';

const componentSource = readFileSync(new URL('../src/components/BrokerImport.jsx', import.meta.url), 'utf8');
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
  assert.match(extractorSource, /getDocument\(\{[\s\S]*data,/);
  assert.match(extractorSource, /pdf\.worker\.min\.mjs\?url/);
});
