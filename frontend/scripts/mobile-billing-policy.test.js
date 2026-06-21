import test from 'node:test';
import assert from 'node:assert/strict';

import {
  finishGooglePlayTransactionIfFinalized,
  shouldFinishGooglePlayTransaction,
} from '../src/mobile/billingPolicy.js';

test('finishes Google Play transactions only after server finalization', () => {
  for (const status of ['applied', 'consume_completed', 'already_applied', 'active']) {
    assert.equal(shouldFinishGooglePlayTransaction({ purchase: { status } }), true, status);
  }
});

test('does not finish Google Play transactions while server consume is pending', () => {
  assert.equal(shouldFinishGooglePlayTransaction({ purchase: { status: 'consume_pending' } }), false);
  assert.equal(shouldFinishGooglePlayTransaction({ purchase: { status: '' } }), false);
  assert.equal(shouldFinishGooglePlayTransaction({}), false);
  assert.equal(shouldFinishGooglePlayTransaction(null), false);
});

test('finishes finalized Google Play transaction and reports result', async () => {
  let finished = false;
  const result = await finishGooglePlayTransactionIfFinalized({
    serverResponse: { purchase: { status: 'applied' } },
    transaction: { finish: async () => { finished = true; } },
  });

  assert.equal(finished, true);
  assert.deepEqual(result, { attempted: true, finished: true, error: '' });
});

test('does not throw when finalized Google Play transaction finish fails', async () => {
  const result = await finishGooglePlayTransactionIfFinalized({
    serverResponse: { purchase: { status: 'active' } },
    transaction: { finish: async () => { throw new Error('finish failed'); } },
  });

  assert.equal(result.attempted, true);
  assert.equal(result.finished, false);
  assert.match(result.error, /finish failed/);
});

test('skips transaction finish while server consume is pending', async () => {
  let finished = false;
  const result = await finishGooglePlayTransactionIfFinalized({
    serverResponse: { purchase: { status: 'consume_pending' } },
    transaction: { finish: async () => { finished = true; } },
  });

  assert.equal(finished, false);
  assert.deepEqual(result, { attempted: false, finished: false, error: '' });
});
