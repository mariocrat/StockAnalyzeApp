import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildGooglePlayRecoveryCandidates,
  selectGooglePlayOffer,
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
        basic_review_15: { google_play_product_id: 'play.basic.15' },
      },
      subscriptions: {
        pro_monthly: { google_play_product_id: 'play.pro.monthly' },
      },
    },
    localReceipts: [
      {
        purchaseToken: 'token-a',
        transactions: [{ products: [{ id: 'play.basic.15' }] }],
      },
      {
        purchaseToken: 'token-a',
        transactions: [{ products: [{ id: 'play.basic.15' }] }],
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
    { localProductId: 'basic_review_15', purchaseToken: 'token-a' },
    { localProductId: 'pro_monthly', purchaseToken: 'token-b' },
  ]);
});

test('selects the configured Pro launch offer even when it is not first', () => {
  const offer = selectGooglePlayOffer({
    storeProduct: {
      offers: [
        { id: 'pro_monthly@monthly' },
        { id: 'pro_monthly@monthly@launch_7900_3m' },
      ],
    },
    productConfig: {
      google_play_product_id: 'pro_monthly',
      google_play_base_plan_id: 'monthly',
      google_play_offer_id: 'launch_7900_3m',
    },
    localProductId: 'pro_monthly',
  });

  assert.equal(offer?.id, 'pro_monthly@monthly@launch_7900_3m');
});

test('falls back to the normal Pro base plan when the launch offer is unavailable', () => {
  const offer = selectGooglePlayOffer({
    storeProduct: { offers: [{ id: 'pro_monthly@monthly' }] },
    localProductId: 'pro_monthly',
  });

  assert.equal(offer?.id, 'pro_monthly@monthly');
});

test('keeps the first Google Play offer for one-time products', () => {
  const offer = selectGooglePlayOffer({
    storeProduct: { offers: [{ id: 'basic_review_15' }] },
    localProductId: 'basic_review_15',
  });

  assert.equal(offer?.id, 'basic_review_15');
});
