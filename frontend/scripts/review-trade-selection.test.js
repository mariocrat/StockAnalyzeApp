import test from 'node:test';
import assert from 'node:assert/strict';
import {
  buildReviewTradeGroups,
  filterReviewTradeGroups,
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

test('the picker shows only the five most recent trade episodes by default', () => {
  const rows = Array.from({ length: 7 }, (_, index) => [
    trade((index * 2) + 1, `2026-07-${String(index + 1).padStart(2, '0')}T09:00`, `00000${index}`, `Stock ${index}`, 'buy', 1),
    trade((index * 2) + 2, `2026-07-${String(index + 1).padStart(2, '0')}T09:05`, `00000${index}`, `Stock ${index}`, 'sell', 1),
  ]).flat();
  const groups = buildReviewTradeGroups(rows);

  assert.equal(filterReviewTradeGroups(groups).length, 5);
  assert.deepEqual(
    filterReviewTradeGroups(groups).map(group => group.name),
    ['Stock 6', 'Stock 5', 'Stock 4', 'Stock 3', 'Stock 2'],
  );
});

test('the picker searches older trades by stock name, code, and date range', () => {
  const rows = [
    trade(1, '2026-06-10T09:00', '017900', 'Gwangjeonja', 'buy', 1),
    trade(2, '2026-06-10T09:05', '017900', 'Gwangjeonja', 'sell', 1),
    trade(3, '2026-07-16T09:00', '004310', 'Hyundai Pharm', 'buy', 1),
    trade(4, '2026-07-16T09:05', '004310', 'Hyundai Pharm', 'sell', 1),
  ];
  const groups = buildReviewTradeGroups(rows);

  assert.deepEqual(
    filterReviewTradeGroups(groups, { query: '017900' }).map(group => group.ticker),
    ['017900'],
  );
  assert.deepEqual(
    filterReviewTradeGroups(groups, { query: 'hyundai' }).map(group => group.ticker),
    ['004310'],
  );
  assert.deepEqual(
    filterReviewTradeGroups(groups, { from: '2026-07-01', to: '2026-07-31' }).map(group => group.ticker),
    ['004310'],
  );
});
