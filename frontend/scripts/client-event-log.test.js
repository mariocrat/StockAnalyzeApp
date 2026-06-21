import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildClientEventPayload,
  reportClientEvent,
} from '../src/utils/clientEventLog.js';

test('buildClientEventPayload redacts secret-like details before sending', () => {
  const payload = buildClientEventPayload({
    eventType: 'google_play_purchase_failed',
    level: 'error',
    message: 'Purchase failed',
    path: '/journal',
    details: {
      productId: 'basic_review_30',
      purchaseToken: 'secret-purchase-token',
      nested: {
        authorization: 'Bearer secret-session-token',
        safe: 'visible',
      },
    },
  });

  const payloadText = JSON.stringify(payload);
  assert.equal(payload.event_type, 'google_play_purchase_failed');
  assert.equal(payload.details.productId, 'basic_review_30');
  assert.equal(payload.details.nested.safe, 'visible');
  assert.doesNotMatch(payloadText, /secret-purchase-token/);
  assert.doesNotMatch(payloadText, /secret-session-token/);
  assert.match(payloadText, /\[redacted\]/);
});

test('reportClientEvent posts with auth header and never throws when reporting fails', async () => {
  const calls = [];
  await reportClientEvent({
    apiBase: 'http://127.0.0.1:8002',
    sessionToken: 'session-token',
    eventType: 'rewarded_ad_failed',
    message: 'Ad failed',
    post: async (url, body, options) => {
      calls.push({ url, body, options });
      throw new Error('network down');
    },
  });

  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, 'http://127.0.0.1:8002/api/client-events');
  assert.equal(calls[0].options.headers.Authorization, 'Bearer session-token');
});
