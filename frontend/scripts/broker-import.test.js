import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { brokerReviewTradeIssue, prepareBrokerReviewInput } from '../src/utils/brokerReviewInput.js';
import { rowDamageMatrix, transactionIdentityMatrix, tradeFields, validTrade } from './fixtures/broker-row-damage.js';
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
const cssSource = readFileSync(new URL('../src/App.css', import.meta.url), 'utf8');

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
  const row = (y, side, amount, settlement, price, transactionTax) => [
    layoutItem('2026.09.02', 57, y),
    layoutItem(side, 107.9, y),
    layoutItem('원익(A032940)', 173.1, y),
    layoutItem('1', 358.9, y),
    layoutItem(amount, 409.9, y),
    layoutItem(settlement, 473.4, y),
    layoutItem(price, 526.1, y),
    layoutItem('1', 584, y),
    layoutItem(transactionTax, 625.9, y),
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
        ...row(rowOneY, '판매', '7,710', '7,694', '7,710', '15'),
        ...row(rowTwoY, '구매', '7,830', '7,831', '7,830', '0'),
      ],
    }],
  };
}

// Cost probes change only cost cells: settlement totals must never supply missing costs.
function tossCostExtraction(fee, transactionTax, tax) {
  const extraction = tossLayoutExtraction();
  const overrides = new Map([[584, fee], [625.9, transactionTax], [669.4, tax]]);
  extraction.pages[0].items = extraction.pages[0].items.map(item => (
    item.y === 237.8 && overrides.has(item.x) ? { ...item, str: overrides.get(item.x) } : item
  ));
  return extraction;
}

function tossPages(dates = ['2026.09.02']) {
  const extraction = tossLayoutExtraction();
  extraction.pages = dates.map((date, index) => ({
    pageNumber: index + 1,
    items: extraction.pages[0].items.map(item => ({ ...item, str: item.str === '2026.09.02' ? date : item.str })),
  }));
  extraction.pageCount = extraction.pages.length;
  return extraction;
}

test('Toss multi-page tables preserve all independent rows and sort dates across repeated headers', () => {
  const extraction = tossPages(['2026.09.02', '2026.09.01', '2026.09.03']);
  const result = parseBrokerStatement(extraction.text, extraction);
  assert.equal(result.status, BROKER_STATEMENT_STATUS.READY);
  assert.deepEqual(result.completeness, { recognizedRows: 6, parsedRows: 6 });
  assert.deepEqual(result.trades.map(row => row.tradeDate), ['2026-09-03', '2026-09-03', '2026-09-02', '2026-09-02', '2026-09-01', '2026-09-01']);
  assert.deepEqual(result.trades.map(row => row.sourceIndex), [4, 5, 0, 1, 2, 3]);
  assert.equal(new Set(result.trades.map(row => row.id)).size, 6);
  assert.deepEqual(result.trades.map(row => [row.fee, row.tax]), [[1, 15], [1, 0], [1, 15], [1, 0], [1, 15], [1, 0]]);
  for (const splitAll of [false, true]) {
    const split = tossPages(['2026.09.02', '2026.09.03']);
    split.pages[1].items = split.pages[1].items.flatMap(item => {
      if (item.y !== 263 || (!splitAll && item.str !== '종목명(종목코드)')) return [item];
      const at = item.str === '종목명(종목코드)' ? 3 : 1;
      return [{ ...item, str: item.str.slice(0, at) }, { ...item, str: item.str.slice(at), x: item.x + at * 2.5, y: item.y + 0.25 }];
    });
    const parsed = parseBrokerStatement(split.text, split);
    assert.equal(parsed.status, BROKER_STATEMENT_STATUS.READY, 'split repeated header');
    assert.deepEqual(parsed.completeness, { recognizedRows: 4, parsedRows: 4 });
    assert.deepEqual(parsed.trades.map(row => [row.side, row.fee, row.tax]), [['sell', 1, 15], ['buy', 1, 0], ['sell', 1, 15], ['buy', 1, 0]]);
  }
});

test('Toss rejects the whole import when one mandatory transaction field is missing or malformed', () => {
  for (const [x, invalid] of [[57, '2026.02.30'], [57, '2026.09.02 extra'], [107.9, '교환'],
    [173.1, '원익(A??????)'], [358.9, 'unknown'], [526.1, '1,,000']]) {
    for (const value of [invalid, '']) {
      const extraction = tossPages(['2026.09.01', '2026.09.02', '2026.09.03']);
      extraction.pages[1].items = extraction.pages[1].items.map(item => item.y === 237.8 && item.x === x ? { ...item, str: value } : item);
      const result = parseBrokerStatement(extraction.text, extraction);
      assert.equal(result.status, BROKER_STATEMENT_STATUS.TOSS_INCOMPLETE, String([x, value]));
      assert.deepEqual(result.trades, []);
      assert.deepEqual(result.completeness, { recognizedRows: 6, parsedRows: 5 });
    }
  }
  assert.match(BROKER_STATEMENT_MESSAGES.TOSS_INCOMPLETE, /일부 거래를 정확히 읽지 못해 가져오기를 중단/);
  const multiple = tossPages();
  multiple.pages[0].items = multiple.pages[0].items.map(item => item.y === 237.8 && [107.9, 173.1].includes(item.x)
    ? { ...item, str: '손상' } : item);
  // With both identity anchors lost, even occupied slots cannot prove this is a trade.
  const unidentifiable = parseBrokerStatement(multiple.text, multiple);
  assert.equal(unidentifiable.status, BROKER_STATEMENT_STATUS.READY);
  assert.deepEqual(unidentifiable.completeness, { recognizedRows: 1, parsedRows: 1 });
  assert.match(componentSource, /statementStatus === BROKER_STATEMENT_STATUS.TOSS_INCOMPLETE/);
  assert.match(componentSource, /role="alert"[\s\S]*BROKER_STATEMENT_MESSAGES.TOSS_INCOMPLETE/);
});

test('Toss tri-state row shapes reject composite damage without guessing non-transaction rows', () => {
  for (const { name, changes, kind } of [...rowDamageMatrix(), ...transactionIdentityMatrix()]) {
    const extraction = tossPages();
    extraction.pages[0].items = extraction.pages[0].items.filter(item => item.y !== 212.6);
    const positions = [57, 107.9, 173.1, 358.9, 526.1];
    extraction.pages[0].items.push(...tradeFields.flatMap((key, index) => {
      const value = Object.hasOwn(changes, key) ? changes[key] : validTrade[index];
      return value === null ? [] : [layoutItem(value, positions[index] + 0.25, 180 + index % 2 * 0.25)];
    }));
    const result = parseBrokerStatement(extraction.text, extraction);
    const incomplete = kind === 'incomplete_transaction';
    const parsed = kind === 'transaction' ? 2 : 1;
    assert.equal(result.status, incomplete ? BROKER_STATEMENT_STATUS.TOSS_INCOMPLETE : BROKER_STATEMENT_STATUS.READY, name);
    assert.deepEqual(result.completeness, { recognizedRows: incomplete ? 2 : parsed, parsedRows: parsed }, name);
    assert.equal(result.trades.length, incomplete ? 0 : parsed, name);
    assert.equal(new Set(result.trades.map(row => row.id)).size, result.trades.length, name);
  }
});

test('Toss headerless damaged or unextracted continuation pages cannot become partial success', () => {
  for (const fault of ['no-header', 'partial-header', 'empty-page', 'missing-page', 'page-order', 'bad-coordinate']) {
    const extraction = tossPages(['2026.09.01', '2026.09.02']);
    const page = extraction.pages[1];
    if (fault === 'no-header') page.items = page.items.filter(item => item.y !== 263);
    if (fault === 'partial-header') page.items = page.items.filter(item => item.str !== '거래구분');
    if (fault === 'empty-page') page.items = [];
    if (fault === 'missing-page') extraction.pages.pop();
    if (fault === 'page-order') page.pageNumber = 1;
    if (fault === 'bad-coordinate') page.items[0].x = NaN;
    const result = parseBrokerStatement(extraction.text, extraction);
    assert.equal(result.status, BROKER_STATEMENT_STATUS.TOSS_INCOMPLETE, fault);
    assert.deepEqual(result.trades, []);
  }
  for (const side of ['구매', '판매']) for (const missing of [true, false])
    for (const shifts of [[0, 0, 0], [0.25, 0, 0], [0, 0.25, 0], [0, 0, 0.25],
      [-0.25, 0, 0], [0, -0.25, 0], [0, 0, -0.25], [0.25, 0.25, 0.25], [0, 20, 20]]) {
    const extraction = tossPages();
    extraction.pages[0].items = extraction.pages[0].items.filter(item => item.y !== 212.6);
    const identityX = new Map([[57, 40], [107.9, 100], [173.1, 165]]);
    extraction.pages[0].items = extraction.pages[0].items.map(item => ({ ...item, x: identityX.get(item.x) ?? item.x }));
    extraction.pages.push({ pageNumber: 2, items: [
      layoutItem('2026.09.03', 40 + shifts[0], 200), layoutItem(side, 100 + shifts[1], 200.25),
      layoutItem('KODEX 200(A069500)', 165 + shifts[2], 199.75),
      ...(missing ? [] : [layoutItem('불명', 358.9, 200), layoutItem('불명', 526.1, 200)]),
    ] });
    extraction.pageCount = 2;
    const result = parseBrokerStatement(extraction.text, extraction);
    assert.equal(result.status, BROKER_STATEMENT_STATUS.TOSS_INCOMPLETE, JSON.stringify({ side, missing, shifts }));
    assert.deepEqual(result.trades, []);
    assert.deepEqual(result.completeness, { recognizedRows: 2, parsedRows: 1 });
  }
});

test('Toss summaries balances and ordinary dated notes are not counted as executions', () => {
  const single = tossPages();
  single.pages[0].items = single.pages[0].items.filter(item => item.y !== 212.6);
  const footer = structuredClone(single);
  footer.pages[0].items.push(layoutItem('2026.09.02', 57, 180), layoutItem('2', 358.9, 180), layoutItem('7,830', 526.1, 180));
  const explanation = structuredClone(single);
  explanation.pages.push({ pageNumber: 2, items: [layoutItem('2026.09.02 기준 KODEX 200(A069500) 안내입니다.', 57, 200)] });
  explanation.pageCount = 2;
  explanation.pages[1].items.push(layoutItem('2026.09.02 구매 시 KODEX 200 (A069500) 안내입니다.', 57, 160));
  const segmentedExplanation = structuredClone(single);
  segmentedExplanation.pages.push({ pageNumber: 2, items: [
    layoutItem('2026.09.02', 57, 200), layoutItem('기준', 120, 200),
    layoutItem('KODEX 200(A069500)', 173.1, 200), layoutItem('안내입니다.', 330, 200),
  ] });
  segmentedExplanation.pageCount = 2;
  const tableExplanation = structuredClone(single);
  tableExplanation.pages[0].items.push(layoutItem('2026.09.02', 57, 180), layoutItem('기준', 107.9, 180),
    layoutItem('KODEX 200(A069500)', 173.1, 180), layoutItem('안내입니다.', 358.9, 180));
  const nonTransactions = [['dated numeric footer', footer], ['headerless prose', explanation],
    ['segmented prose', segmentedExplanation], ['prose below a table header', tableExplanation]];
  for (const side of ['구매', '판매']) {
    const splitInstruction = structuredClone(single);
    const identityX = new Map([[57, 40], [107.9, 100], [173.1, 165]]);
    splitInstruction.pages[0].items = splitInstruction.pages[0].items.map(item => ({
      ...item, x: identityX.get(item.x) ?? item.x,
    }));
    splitInstruction.pages.push({ pageNumber: 2, items: [
      layoutItem('2026.09.02', 40, 200), layoutItem(side, 100, 200), layoutItem('시', 135, 200),
      layoutItem('KODEX 200(A069500)', 165, 200), layoutItem('안내입니다.', 330, 200),
    ] });
    splitInstruction.pageCount = 2;
    nonTransactions.push([side + ' split instruction', splitInstruction]);
    for (const [index, x] of [[1, 145], [2, 270]]) {
      const misplaced = structuredClone(splitInstruction);
      misplaced.pages[1].items.splice(2, 1);
      misplaced.pages[1].items.pop();
      misplaced.pages[1].items[index].x = x;
      nonTransactions.push([side + ' misaligned identity ' + index, misplaced]);
    }
    for (const x of [120, 130, 145]) {
      const nearSide = structuredClone(splitInstruction);
      nearSide.pages[1].items[2].x = x;
      nonTransactions.push([side + ' prose fragment at ' + x, nearSide]);
    }
  }
  for (const [name, input] of nonTransactions) {
    const result = parseBrokerStatement(input.text, input);
    assert.equal(result.status, BROKER_STATEMENT_STATUS.READY, name);
    assert.deepEqual(result.completeness, { recognizedRows: 1, parsedRows: 1 }, name);
    assert.equal(result.trades.length, 1, name);
    assert.deepEqual([result.trades[0].side, result.trades[0].fee, result.trades[0].tax], ['sell', 1, 15], name);
  }
  const extraction = tossPages();
  extraction.pages[0].items.push(
    layoutItem('2026.09.02', 57, 180), layoutItem('잔고', 107.9, 180), layoutItem('원익(A032940)', 173.1, 180),
    layoutItem('합계', 57, 160), layoutItem('2', 358.9, 160), layoutItem('15,540', 409.9, 160),
    layoutItem('주의사항: 발급일 2026.09.02 기준입니다.', 57, 140),
    layoutItem('합계', 57, 120), layoutItem('원익(A032940)', 173.1, 120), layoutItem('2', 358.9, 120), layoutItem('7,830', 526.1, 120),
  );
  extraction.pages.push({ pageNumber: 2, items: [layoutItem('합계 2건 / 잔고 안내', 57, 200)] });
  extraction.pageCount = 2;
  const result = parseBrokerStatement(extraction.text, extraction);
  assert.equal(result.status, BROKER_STATEMENT_STATUS.READY);
  assert.deepEqual(result.completeness, { recognizedRows: 2, parsedRows: 2 });
});

test('Toss explicit instrument code boundaries admit numeric names without guessing generic numeric prefixes', () => {
  const extraction = tossPages();
  let instrument = 0;
  extraction.pages[0].items = extraction.pages[0].items.map(item => item.str === '원익(A032940)'
    ? { ...item, str: ['KODEX 200(A069500)', 'TIGER 200(A102110)'][instrument++] } : item);
  const result = parseBrokerStatement(extraction.text, extraction);
  assert.equal(result.status, BROKER_STATEMENT_STATUS.READY);
  assert.deepEqual(result.trades.map(row => [row.stockName, row.symbol]), [['KODEX 200', '069500'], ['TIGER 200', '102110']]);
  assert.deepEqual(parseTradeCandidates('2026-09-02 구매 KODEX 200 069500 70,000원 1주'), []);
});

test('Toss text-only fallback also refuses to silently drop an identifiable broken execution', () => {
  for (const broken of ['2026-09-02 판매 삼성전자 005930 가격불명 1주',
    '판매 삼성전자 005930 70,000원 1주', '2026-09-02 교환 삼성전자 005930 70,000원 1주']) {
    const result = parseBrokerStatement('토스증권 국내주식\n2026-09-02 구매 삼성전자 005930 70,000원 1주\n' + broken);
    assert.equal(result.status, BROKER_STATEMENT_STATUS.TOSS_INCOMPLETE);
    assert.deepEqual(result.trades, []);
    assert.deepEqual(result.completeness, { recognizedRows: 2, parsedRows: 1 });
  }
});

test('confirmation issues use the same instrument and cost boundary as review preparation', () => {
  const valid = parseBrokerStatement(tossLayoutExtraction().text, tossLayoutExtraction()).trades[0];
  assert.equal(brokerReviewTradeIssue(valid), '');
  for (const side of ['buy', 'sell']) {
    for (const [delta, label] of [[{ fee: null }, '수수료'], [{ tax: undefined }, '세금'],
      [{ fee: null, tax: null }, '수수료와 세금'], [{ fee: '0' }, '수수료'], [{ tax: -1 }, '세금'], [{ fee: NaN }, '수수료']]) {
      const row = { ...valid, side, ...delta };
      const message = `${label} 정보가 없어 복기를 준비할 수 없습니다.`;
      assert.equal(brokerReviewTradeIssue(row), message);
      assert.throws(() => prepareBrokerReviewInput([row]), { message });
    }
  }
  const nameOnly = parseTradeCandidates('2026-09-02 삼성전자 매수 1주 @ 70,000')[0];
  assert.ok(nameOnly);
  assert.equal(nameOnly.symbol, null);
  assert.match(brokerReviewTradeIssue(nameOnly), /종목명과 6자리 종목코드/);
  assert.throws(() => prepareBrokerReviewInput([nameOnly]), { message: brokerReviewTradeIssue(nameOnly) });
  assert.equal(brokerReviewTradeIssue({ ...valid, fee: 0, tax: 0 }), '');
});

test('generic sides accept explicit purchase and sale labels and reject ambiguous directions', () => {
  for (const [label, expected] of [['구매', 'buy'], ['매수', 'buy'], ['BUY', 'buy'],
    ['판매', 'sell'], ['매도', 'sell'], ['SELL', 'sell']]) {
    const parsed = parseTradeCandidates(`2026-09-02 ${label} 삼성전자 005930 70,000원 1주`);
    assert.equal(parsed.length, 1, label);
    assert.equal(parsed[0].side, expected, label);
    assert.equal(parsed[0].fee, null);
    assert.equal(parsed[0].tax, null);
  }
  for (const label of ['매수취소', '구매취소', '재매수', '매수/매도', '매수 매도', '교환', 'BUYBACK']) {
    assert.deepEqual(parseTradeCandidates(`2026-09-02 ${label} 삼성전자 005930 70,000원 1주`), [], label);
  }
});

test('Toss cost columns preserve nonzero values and explicit zero independently', () => {
  for (const [fee, transactionTax, tax, expected] of [
    ['1,234.5', '15', '2', [1234.5, 17]],
    ['0', '0', '0', [0, 0]],
    ['0.00', '0.0', '0', [0, 0]],
  ]) {
    const extraction = tossCostExtraction(fee, transactionTax, tax);
    const parsed = parseBrokerStatement(extraction.text, extraction);
    assert.equal(parsed.status, BROKER_STATEMENT_STATUS.READY);
    assert.equal(parsed.trades.length, 2);
    assert.deepEqual(parsed.trades.map(row => row.side), ['sell', 'buy']);
    assert.deepEqual([parsed.trades[0].fee, parsed.trades[0].tax], expected);
    assert.deepEqual([parsed.trades[0].price, parsed.trades[0].quantity], [7710, 1]);
    assert.deepEqual([parsed.trades[1].fee, parsed.trades[1].tax], [1, 0]);
  }
});

test('missing or malformed Toss cost components stay unknown without discarding the trade', () => {
  for (const bad of [null, '', '-', '-1', '1,,000', '1 2', 'NaN', 'Infinity', 'unknown', '9007199254740992']) {
    for (const column of [0, 1, 2]) {
      const values = ['1', '15', '0'];
      values[column] = bad;
      const extraction = tossCostExtraction(...values);
      const parsed = parseBrokerStatement(extraction.text, extraction);
      assert.equal(parsed.status, BROKER_STATEMENT_STATUS.READY);
      assert.equal(parsed.trades.length, 2);
      const row = parsed.trades[0];
      assert.equal(row.fee, column === 0 ? null : 1);
      assert.equal(row.tax, column === 0 ? 15 : null);
      assert.throws(() => prepareBrokerReviewInput([row]), /정보가 없어 복기를 준비할 수 없습니다/);
    }
  }
  for (const header of ['수수료', '거래세', '제세금']) {
    const extraction = tossLayoutExtraction();
    extraction.pages[0].items = extraction.pages[0].items.filter(item => item.str !== header);
    const row = parseBrokerStatement(extraction.text, extraction).trades[0];
    assert.equal(header === '수수료' ? row.fee : row.tax, null);
    assert.throws(() => prepareBrokerReviewInput([row]), /정보가 없어 복기를 준비할 수 없습니다/);
  }
});

test('broker review preparation cannot replace unknown costs with numeric defaults', () => {
  const extraction = tossLayoutExtraction();
  const rows = parseBrokerStatement(extraction.text, extraction).trades.map((row, index) => ({
    ...row, tradeTime: index ? '09:30' : '14:10', timeUnknown: false,
  }));
  const before = structuredClone(rows);
  const prepared = prepareBrokerReviewInput(rows).groups[0];
  assert.deepEqual(prepared.trades.map(row => [row.side, row.fee, row.tax]), [['buy', 1, 0], ['sell', 1, 15]]);
  assert.deepEqual(rows, before);
  for (const field of ['fee', 'tax']) {
    for (const value of [null, undefined, '', '0', false, NaN, Infinity, -1]) {
      const unknown = rows.map(row => ({ ...row, [field]: value }));
      const snapshot = structuredClone(unknown);
      assert.throws(() => prepareBrokerReviewInput(unknown), /정보가 없어 복기를 준비할 수 없습니다/);
      assert.deepEqual(unknown, snapshot);
    }
  }
  const zero = prepareBrokerReviewInput(rows.map(row => ({ ...row, fee: 0, tax: 0 }))).groups[0];
  assert.ok(zero.trades.every(row => row.fee === 0 && row.tax === 0));
  const generic = parseTradeCandidates('2026-09-02 삼성전자 005930 구매 70,000원 1주');
  assert.throws(() => prepareBrokerReviewInput(generic), { message: '수수료와 세금 정보가 없어 복기를 준비할 수 없습니다.' });
});

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
  assert.deepEqual(parsed.trades.map(trade => [trade.fee, trade.tax]), [[1, 15], [1, 0]]);
});

test('requires actual foreign trade evidence before returning overseas unsupported', () => {
  const emptyDollarSection = '달러 거래내역\n- 표시할 내역이 없습니다 -';
  const actualOverseasTrade = '달러 거래내역\n2026-08-27 US0378331005 매수 10주 @ $ 70,000';

  assert.equal(detectBrokerStatement(emptyDollarSection).market, 'unknown');
  assert.equal(parseBrokerStatement(emptyDollarSection).status, BROKER_STATEMENT_STATUS.NO_CANDIDATES);
  assert.equal(detectBrokerStatement(actualOverseasTrade).market, 'overseas');
  assert.equal(parseBrokerStatement(actualOverseasTrade).status, BROKER_STATEMENT_STATUS.OVERSEAS_UNSUPPORTED);
  assert.deepEqual(parseBrokerStatement(actualOverseasTrade).trades, []);
  const domestic = tossPages();
  const mixed = parseBrokerStatement(domestic.text + '\n' + actualOverseasTrade, domestic);
  assert.equal(mixed.status, BROKER_STATEMENT_STATUS.OVERSEAS_UNSUPPORTED);
  assert.deepEqual(mixed.trades, []);
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

  assert.equal(componentSource.includes('disabled={timeRequired && timeUnknown}'), true);
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

test('disables broker transfer until a trade is selected and required times are complete', () => {
  assert.match(componentSource, /const canImportSelectedTrades = selectedTrades\.length > 0 && selectedTimeValidation\.valid/);
  assert.match(componentSource, /disabled=\{!canImportSelectedTrades\}/);
  assert.match(componentSource, />\s*매매 복기로 가져오기\s*<\/button>/);
  assert.doesNotMatch(componentSource, /선택한 거래를 매매복기로 가져오기/);
  assert.match(componentSource, /거래를 선택하면 매매 복기로 가져올 수 있습니다/);
  assert.match(componentSource, /필수 체결시간을 입력하면 매매 복기로 가져올 수 있습니다/);
  assert.match(cssSource, /\.broker-trade-card \{[\s\S]*?grid-template-areas:/);
  assert.match(cssSource, /\.broker-trade-time \{[\s\S]*?grid-area: time/);
});

test('CTA policy enables only reviewable selected trade sets', () => {
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
  const canTransfer = rows => rows.length > 0 && validateTradeTimesForReview(rows).valid;

  assert.equal(canTransfer([]), false);
  assert.equal(canTransfer([trade('buy'), trade('sell', { side: 'sell' })]), false);
  assert.equal(canTransfer([
    trade('buy', { tradeTime: '09:30', timeUnknown: false }),
    trade('sell', { side: 'sell', tradeTime: '14:10', timeUnknown: false }),
  ]), true);
  assert.equal(canTransfer([trade('buy')]), true);
  assert.equal(canTransfer([trade('buy'), trade('sell', { tradeDate: '2026-09-03', side: 'sell' })]), true);

  const parsed = parseBrokerStatement(tossLayoutExtraction().text, tossLayoutExtraction()).trades
    .map(row => ({ ...row, ...createTradeTimeState(row.tradeTime) }));
  const before = structuredClone(parsed);
  assert.throws(() => prepareBrokerReviewInput(parsed), /체결시간/);
  const timed = parsed.map(row => ({ ...row, tradeTime: row.side === 'buy' ? '09:30' : '14:10', timeUnknown: false }));
  const prepared = prepareBrokerReviewInput(timed);
  assert.equal(prepared.groups.length, 1);
  const group = prepared.groups[0];
  assert.equal(group.targetTradeId, null);
  assert.deepEqual(group.trades.map(row => [row.ticker, row.side, row.price, row.quantity, row.trade_date]), [
    ['032940', 'buy', 7830, 1, '2026-09-02T09:30'],
    ['032940', 'sell', 7710, 1, '2026-09-02T14:10'],
  ]);
  for (const row of group.trades) {
    assert.deepEqual(Object.keys(row).sort(), ['trade_date', 'ticker', 'name', 'side', 'price', 'quantity', 'fee', 'tax', 'memo', 'source'].sort());
    assert.equal('id' in row, false);
  }
  assert.deepEqual(new Set(group.previewTrades.map(row => row.previewId)), new Set(parsed.map(row => row.id)));
  assert.deepEqual(parsed, before);

  // All of BUY/SELL/BUY require explicit times; rows never become inferred episodes.
  const mixed = [timed.find(row => row.side === 'buy'), timed.find(row => row.side === 'sell'),
    { ...timed.find(row => row.side === 'buy'), id: 'pdf-trade-third', tradeTime: null, timeUnknown: true }];
  assert.throws(() => prepareBrokerReviewInput(mixed), /체결시간/);
  const repeated = prepareBrokerReviewInput(mixed.map((row, index) => ({ ...row, tradeTime: `1${index}:00`, timeUnknown: false })));
  assert.equal(repeated.groups.length, 1);
  assert.equal(repeated.groups[0].trades.length, 3);

  for (const side of ['buy', 'sell']) {
    const optional = parsed.filter(row => row.side === side);
    const rows = [optional[0], { ...optional[0], id: 'pdf-trade-repeat' }];
    const result = prepareBrokerReviewInput(rows).groups[0];
    assert.equal(result.trades.length, 2);
    assert.ok(result.previewTrades.every(row => row.timeUnknown && row.tradeTime === null));
    assert.ok(result.trades.every(row => row.trade_date === '2026-09-02'));
  }
  const dates = parsed.map((row, index) => ({ ...row, tradeDate: `2026-09-0${index + 2}` }));
  assert.equal(prepareBrokerReviewInput(dates).groups[0].trades.length, 2);
  const unknownWithStaleTime = { ...parsed[0], tradeTime: '10:00', timeUnknown: true };
  assert.equal(prepareBrokerReviewInput([unknownWithStaleTime]).groups[0].trades[0].trade_date, '2026-09-02');
  assert.throws(() => prepareBrokerReviewInput([]), /선택/);
  assert.throws(() => prepareBrokerReviewInput([{ ...parsed[0], price: NaN }]), /확인/);
  assert.throws(() => prepareBrokerReviewInput([{ ...parsed[0], tradeDate: '2026-02-30' }]), /확인/);
  const separate = prepareBrokerReviewInput([parsed[0], { ...parsed[1], symbol: '005930', stockName: '삼성전자' }]);
  assert.equal(separate.groups.length, 2);
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
