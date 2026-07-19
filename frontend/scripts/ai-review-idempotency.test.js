import test from 'node:test';
import assert from 'node:assert/strict';

import { buildAiReviewIdempotencyKey } from '../src/utils/aiReviewIdempotency.js';

const trades = [
  {
    id: 1,
    trade_date: '2026-06-21T10:30',
    ticker: '005930',
    name: 'Samsung',
    side: 'buy',
    price: 70000,
    quantity: 1,
  },
];

test('builds the same AI review idempotency key for an exact retry of one request', () => {
  const first = buildAiReviewIdempotencyKey({ trades, reviewType: 'basic', requestNonce: 'request-1' });
  const second = buildAiReviewIdempotencyKey({
    trades: [{ ...trades[0] }],
    reviewType: 'basic',
    requestNonce: 'request-1',
  });

  assert.equal(first, second);
  assert.match(first, /^ai-review-/);
});

test('uses a new key for an intentional rerun while keeping review types separate', () => {
  const basic = buildAiReviewIdempotencyKey({ trades, reviewType: 'basic', requestNonce: 'request-1' });
  const advanced = buildAiReviewIdempotencyKey({ trades, reviewType: 'advanced', requestNonce: 'request-1' });
  const rerun = buildAiReviewIdempotencyKey({ trades, reviewType: 'basic', requestNonce: 'request-2' });

  assert.notEqual(basic, advanced);
  assert.notEqual(basic, rerun);
});
