import test from 'node:test';
import assert from 'node:assert/strict';
import {
  buildReviewTradeGroups,
  findReviewTradeGroup,
  reviewTradesForGroup,
} from '../src/utils/reviewTradeSelection.js';

const trade = (id, tradeDate, ticker, name, side, quantity) => ({
  id,
  trade_date: tradeDate,
  ticker,
  name,
  side,
  quantity,
  price: 1000 + id,
});

test('buy and sell fills are grouped into one completed trade episode', () => {
  const rows = [
    trade(1, '2026-07-10T09:31', '017900', '광전자', 'buy', 10),
    trade(2, '2026-07-10T09:36', '017900', '광전자', 'buy', 5),
    trade(3, '2026-07-10T09:38', '017900', '광전자', 'sell', 15),
  ];
  const groups = buildReviewTradeGroups(rows);

  assert.equal(groups.length, 1);
  assert.deepEqual(groups[0].trades.map(row => row.id), [1, 2, 3]);
  assert.equal(groups[0].buyCount, 2);
  assert.equal(groups[0].sellCount, 1);
});

test('different stocks and repeated round trips remain separately selectable', () => {
  const rows = [
    trade(1, '2026-07-10T09:31', '017900', '광전자', 'buy', 10),
    trade(2, '2026-07-10T09:38', '017900', '광전자', 'sell', 10),
    trade(3, '2026-07-16T09:06', '004310', '현대약품', 'buy', 5),
    trade(4, '2026-07-16T09:10', '004310', '현대약품', 'sell', 5),
    trade(5, '2026-07-20T10:00', '017900', '광전자', 'buy', 3),
    trade(6, '2026-07-20T10:05', '017900', '광전자', 'sell', 3),
  ];
  const groups = buildReviewTradeGroups(rows);

  assert.equal(groups.length, 3);
  assert.deepEqual(groups.map(group => group.trades.map(row => row.id)), [[5, 6], [3, 4], [1, 2]]);
  const historical = findReviewTradeGroup(groups, rows[0]);
  assert.deepEqual(reviewTradesForGroup(groups, historical.key).map(row => row.id), [1, 2]);
});

test('selecting one saved trade never includes a newly entered different stock', () => {
  const gwangjeonja = [
    trade(1, '2026-07-10T09:31', '017900', '광전자', 'buy', 10),
    trade(2, '2026-07-10T09:38', '017900', '광전자', 'sell', 10),
  ];
  const hyundai = [
    trade(3, '2026-07-16T09:06', '004310', '현대약품', 'buy', 5),
    trade(4, '2026-07-16T09:10', '004310', '현대약품', 'sell', 5),
  ];
  const groups = buildReviewTradeGroups([...gwangjeonja, ...hyundai]);
  const selected = findReviewTradeGroup(groups, gwangjeonja[1]);

  assert.deepEqual(reviewTradesForGroup(groups, selected.key).map(row => row.ticker), ['017900', '017900']);
});
