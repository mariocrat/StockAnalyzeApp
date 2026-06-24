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

test('builds the same AI review idempotency key for equivalent retry payloads in the same time bucket', () => {
  const first = buildAiReviewIdempotencyKey({ trades, reviewType: 'basic', nowMs: 60_001 });
  const second = buildAiReviewIdempotencyKey({ trades: [{ ...trades[0] }], reviewType: 'basic', nowMs: 119_999 });

  assert.equal(first, second);
  assert.match(first, /^ai-review-/);
});

test('changes AI review idempotency key when review type or time bucket changes', () => {
  const basic = buildAiReviewIdempotencyKey({ trades, reviewType: 'basic', nowMs: 60_001 });
  const advanced = buildAiReviewIdempotencyKey({ trades, reviewType: 'advanced', nowMs: 60_001 });
  const later = buildAiReviewIdempotencyKey({ trades, reviewType: 'basic', nowMs: 120_000 });

  assert.notEqual(basic, advanced);
  assert.notEqual(basic, later);
});
