import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildGooglePlayRecoveryCandidates,
  shouldFinishGooglePlayTransaction,
} from '../src/mobile/billingPolicy.js';

test('does not finish Google Play transactions after server finalization', () => {
  for (const status of ['applied', 'consume_completed', 'already_applied', 'active']) {
    assert.equal(shouldFinishGooglePlayTransaction({ purchase: { status } }), false, status);
  }
});

test('does not finish Google Play transactions while server consume is pending', () => {
  assert.equal(shouldFinishGooglePlayTransaction({ purchase: { status: 'consume_pending' } }), false);
  assert.equal(shouldFinishGooglePlayTransaction({ purchase: { status: '' } }), false);
  assert.equal(shouldFinishGooglePlayTransaction({}), false);
  assert.equal(shouldFinishGooglePlayTransaction(null), false);
});

test('builds Google Play recovery candidates from local receipts without duplicates', () => {
  const candidates = buildGooglePlayRecoveryCandidates({
    productCatalog: {
      consumables: {
        basic_review_30: { google_play_product_id: 'play.basic.30' },
      },
      subscriptions: {
        pro_monthly: { google_play_product_id: 'play.pro.monthly' },
      },
    },
    localReceipts: [
      {
        purchaseToken: 'token-a',
        transactions: [{ products: [{ id: 'play.basic.30' }] }],
      },
      {
        purchaseToken: 'token-a',
        transactions: [{ products: [{ id: 'play.basic.30' }] }],
      },
      {
        purchaseToken: 'token-b',
        transactions: [{ products: [{ id: 'play.pro.monthly' }] }],
      },
      {
        purchaseToken: 'token-c',
        transactions: [{ products: [{ id: 'unknown.product' }] }],
      },
    ],
  });

  assert.deepEqual(candidates, [
    { localProductId: 'basic_review_30', purchaseToken: 'token-a' },
    { localProductId: 'pro_monthly', purchaseToken: 'token-b' },
  ]);
});
