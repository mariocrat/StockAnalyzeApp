import test from 'node:test';
import assert from 'node:assert/strict';

import {
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
