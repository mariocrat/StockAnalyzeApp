import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import {
  BROKER_STATEMENT_MESSAGES,
  BROKER_STATEMENT_STATUS,
  REVIEW_TIME_VALIDATION_MESSAGES,
  createTradeTimeState,
  detectBrokerStatement,
  formatTradeDateTime,
  getRequiredTradeTimeGroups,
  getTradeTimeGroupKey,
  normalizeOptionalTradeTime,
  parseBrokerStatement,
  parseTradeCandidates,
  setTradeTimeUnknownState,
  sortTradesByDateDesc,
  updateTradeTimeState,
  validateTradeTimesForReview,
} from '../src/utils/brokerImport.js';

const componentSource = readFileSync(new URL('../src/components/BrokerImport.jsx', import.meta.url), 'utf8');
const journalSource = readFileSync(new URL('../src/components/TradingJournal.jsx', import.meta.url), 'utf8');
const extractorSource = readFileSync(new URL('../src/utils/pdfTextExtractor.js', import.meta.url), 'utf8');

function layoutItem(str, x, y) {
  return { str, x, y };
}

function tossLayoutExtraction() {
  const headerY = 263;
  const rowOneY = 237.8;
  const rowTwoY = 212.6;
  const columns = [
    ['거래일자', 57],
    ['거래구분', 107.9],
    ['종목명(종목코드)', 173.1],
    ['환율', 313.1],
    ['거래수량', 336.8],
    ['거래대금', 402.2],
    ['정산금액', 467.6],
    ['단가', 530.9],
    ['수수료', 568.2],
    ['거래세', 611.8],
    ['제세금', 655.3],
    ['변제/연체합', 684.1],
    ['잔고', 748.7],
    ['잔액', 772.3],
  ];
  const row = (y, side, amount, settlement, price) => [
    layoutItem('2026.09.02', 57, y),
    layoutItem(side, 107.9, y),
    layoutItem('원익(A032940)', 173.1, y),
    layoutItem('1', 358.9, y),
    layoutItem(amount, 409.9, y),
    layoutItem(settlement, 473.4, y),
    layoutItem(price, 526.1, y),
    layoutItem('1', 584, y),
    layoutItem('0', 625.9, y),
    layoutItem('0', 669.4, y),
    layoutItem('0', 713, y),
    layoutItem('9,727', 766.4, y),
  ];
  const text = [
    '원화-외화 거래구분 원화',
    '원화 거래내역',
    '거래일자 거래구분 종목명(종목코드) 환율 거래수량 거래대금 정산금액 단가 수수료 거래세 제세금 변제/연체합 잔고 잔액',
    '2026.09.02 판매 원익(A032940) 1 7,710 7,694 7,710 1 15 0 0 -1 17,558',
    '2026.09.02 구매 원익(A032940) 1 7,830 7,831 7,830 1 0 0 0 0 9,727',
    '달러 거래내역',
    '- 표시할 내역이 없습니다 -',
  ].join('\\n');
  return {
    text,
    pages: [{
      pageNumber: 1,
      items: [
        ...columns.map(([label, x]) => layoutItem(label, x, headerY)),
        ...row(rowOneY, '판매', '7,710', '7,694', '7,710'),
        ...row(rowTwoY, '구매', '7,830', '7,831', '7,830'),
      ],
    }],
  };
}

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

test('keeps a domestic Toss statement domestic when its dollar section is explicitly empty', () => {
  const tossDomesticMockStatementText = [
    '토스증권 국내주식 거래내역서',
    '원화 거래내역',
    '2026-08-27 삼성전자 005930 매수 10주 @ 70,000',
    '2026-08-27 SK하이닉스 000660 매도 250,000원 2주',
    '달러 거래내역',
    '- 표시할 내역이 없습니다 -',
  ].join('\n');

  const detection = detectBrokerStatement(tossDomesticMockStatementText);
  const parsed = parseBrokerStatement(tossDomesticMockStatementText);

  assert.equal(detection.market, 'domestic');
  assert.equal(detection.hasOverseasMarker, false);
  assert.equal(parsed.status, BROKER_STATEMENT_STATUS.READY);
  assert.deepEqual(parsed.trades.map(trade => trade.symbol), ['005930', '000660']);
  assert.deepEqual(parsed.trades.map(trade => trade.tradeTime), [null, null]);
  assert.deepEqual(parsed.trades.map(trade => [trade.price, trade.quantity]), [[70000, 10], [250000, 2]]);
  assert.equal(new Set(parsed.trades.map(trade => trade.id)).size, 2);
});

test('parses Toss domestic table columns from PDF.js coordinates and normalizes A-prefixed codes', () => {
  const extraction = tossLayoutExtraction();
  const parsed = parseBrokerStatement(extraction.text, extraction);

  assert.equal(parsed.status, BROKER_STATEMENT_STATUS.READY);
  assert.deepEqual(parsed.detection, {
    broker: 'toss',
    market: 'domestic',
    currency: 'krw',
    hasTossMarker: true,
    hasOverseasMarker: false,
    hasDomesticMarker: true,
  });
  assert.deepEqual(parsed.trades.map(trade => ({
    tradeDate: trade.tradeDate,
    side: trade.side,
    stockName: trade.stockName,
    rawSymbol: trade.rawSymbol,
    symbol: trade.symbol,
    quantity: trade.quantity,
    price: trade.price,
    tradeTime: trade.tradeTime,
  })), [
    {
      tradeDate: '2026-09-02',
      side: 'sell',
      stockName: '원익',
      rawSymbol: 'A032940',
      symbol: '032940',
      quantity: 1,
      price: 7710,
      tradeTime: null,
    },
    {
      tradeDate: '2026-09-02',
      side: 'buy',
      stockName: '원익',
      rawSymbol: 'A032940',
      symbol: '032940',
      quantity: 1,
      price: 7830,
      tradeTime: null,
    },
  ]);
  assert.equal(new Set(parsed.trades.map(trade => trade.id)).size, 2);
  assert.deepEqual(parsed.trades.map(trade => trade.sourceIndex), [0, 1]);
});

test('requires actual foreign trade evidence before returning overseas unsupported', () => {
  const emptyDollarSection = '달러 거래내역\n- 표시할 내역이 없습니다 -';
  const actualOverseasTrade = '달러 거래내역\n2026-08-27 US0378331005 매수 10주 @ $ 70,000';

  assert.equal(detectBrokerStatement(emptyDollarSection).market, 'unknown');
  assert.equal(parseBrokerStatement(emptyDollarSection).status, BROKER_STATEMENT_STATUS.NO_CANDIDATES);
  assert.equal(detectBrokerStatement(actualOverseasTrade).market, 'overseas');
  assert.equal(parseBrokerStatement(actualOverseasTrade).status, BROKER_STATEMENT_STATUS.OVERSEAS_UNSUPPORTED);
  assert.deepEqual(parseBrokerStatement(actualOverseasTrade).trades, []);
});

test('keeps execution time optional and never invents it', () => {
  const trade = parseTradeCandidates('2026-08-27 삼성전자 매수 10주 @ 70,000')[0];

  assert.equal(trade.tradeTime, null);
  assert.equal(normalizeOptionalTradeTime('09:10'), '09:10');
  assert.equal(normalizeOptionalTradeTime('25:00'), null);
  assert.equal(normalizeOptionalTradeTime(''), null);
});

test('requires times only for selected same-day same-symbol mixed-side groups', () => {
  const trade = (id, overrides = {}) => ({
    id,
    tradeDate: '2026-09-02',
    stockName: '삼성전자',
    symbol: '005930',
    side: 'buy',
    tradeTime: null,
    timeUnknown: true,
    ...overrides,
  });

  assert.equal(getTradeTimeGroupKey(trade('buy-1')), '2026-09-02|005930');
  assert.equal(validateTradeTimesForReview([
    trade('buy-1', { tradeDate: '2026-09-01' }),
    trade('sell-1', { tradeDate: '2026-09-03', side: 'sell' }),
  ]).valid, true);
  assert.equal(validateTradeTimesForReview([
    trade('buy-1'),
    trade('buy-2'),
  ]).valid, true);
  assert.equal(validateTradeTimesForReview([
    trade('sell-1', { side: 'sell' }),
    trade('sell-2', { side: 'sell' }),
  ]).valid, true);

  const mixed = validateTradeTimesForReview([
    trade('buy-1'),
    trade('sell-1', { side: 'sell' }),
  ]);
  const mixedGroups = getRequiredTradeTimeGroups([
    trade('buy-1'),
    trade('sell-1', { side: 'sell' }),
  ]);
  assert.equal(mixed.valid, false);
  assert.equal(mixedGroups.length, 1);
  assert.equal(mixedGroups[0].key, '2026-09-02|005930');
  assert.equal(mixedGroups[0].buyCount, 1);
  assert.equal(mixedGroups[0].sellCount, 1);
  assert.deepEqual(mixed.requiredTradeIds, ['buy-1', 'sell-1']);
  assert.deepEqual(mixed.missingTradeIds, ['buy-1', 'sell-1']);
  assert.equal(mixed.requiredGroups.length, 1);
  assert.match(REVIEW_TIME_VALIDATION_MESSAGES.REQUIRED_GROUP, /같은 날 매수와 매도가 함께 선택되었습니다/);
  assert.match(REVIEW_TIME_VALIDATION_MESSAGES.REQUIRED_GROUP, /체결시간이 필요합니다/);

  const completed = validateTradeTimesForReview([
    trade('buy-1', { tradeTime: '09:37', timeUnknown: false }),
    trade('sell-1', { side: 'sell', tradeTime: '13:12', timeUnknown: false }),
  ]);
  assert.equal(completed.valid, true);
  assert.equal(completed.requiredGroups.length, 1);
  assert.deepEqual(completed.missingTradeIds, []);

  const mixedSymbols = validateTradeTimesForReview([
    trade('buy-1'),
    trade('sell-1', { side: 'sell' }),
    trade('buy-2'),
    trade('naver-buy', { stockName: 'NAVER', symbol: '035420' }),
  ]);
  assert.equal(mixedSymbols.valid, false);
  assert.deepEqual(mixedSymbols.requiredTradeIds, ['buy-1', 'sell-1', 'buy-2']);
  assert.deepEqual(mixedSymbols.missingTradeIds, ['buy-1', 'sell-1', 'buy-2']);
  assert.equal(mixedSymbols.requiredGroups.some(group => group.symbol === '035420'), false);

  const partial = validateTradeTimesForReview([
    trade('buy-1', { tradeTime: '09:37', timeUnknown: false }),
    trade('sell-1', { side: 'sell' }),
    trade('buy-2'),
  ]);
  assert.deepEqual(partial.missingTradeIds, ['sell-1', 'buy-2']);

  assert.equal(getTradeTimeGroupKey(trade('name-only', { symbol: '' })), null);
  assert.equal(validateTradeTimesForReview([
    trade('name-buy', { symbol: '' }),
    trade('name-sell', { symbol: '', side: 'sell' }),
  ]).valid, true);
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
  assert.match(componentSource, /parseBrokerStatement\(extraction\.text, extraction\)/);
  assert.match(componentSource, /validateTradeTimesForReview/);
  assert.match(componentSource, /체결시간\(필수\)/);
  assert.match(componentSource, /statementStatus: parsed\.status/);
  assert.match(componentSource, /fileName: file\.name/);
  assert.match(componentSource, /선택한 파일/);
  assert.match(componentSource, /selectedTimeValidation\.requiredGroups\.length > 0/);
  assert.match(componentSource, /거래내역서에 체결시간이 없는 경우 비워둘 수 있습니다/);
  assert.match(componentSource, /같은 날 같은 종목의 매수와 매도가 함께 선택되어 있습니다/);
  assert.match(componentSource, /해외주식 거래내역은 아직 지원하지 않습니다/);
  assert.match(componentSource, /거래내역을 인식하지 못했습니다/);
  assert.match(componentSource, /state\.statementStatus === BROKER_STATEMENT_STATUS\.READY/);
  assert.match(componentSource, /다른 PDF 선택/);
  assert.doesNotMatch(componentSource, /<h3>거래 후보<\/h3>/);
  assert.match(extractorSource, /getDocument\(\{[\s\S]*data,/);
  assert.match(extractorSource, /pdf\.worker\.min\.mjs\?url/);
  assert.match(extractorSource, /items: \(content\.items \|\| \[\]\)/);
  assert.match(journalSource, /validateTradeTimesForReview/);
  assert.match(journalSource, /체결시간\(필수\)/);
});
