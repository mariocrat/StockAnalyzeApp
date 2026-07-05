import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

import {
  buildClientEventPayload,
  getStoredAuthSessionToken,
  installGlobalClientEventReporting,
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
    post: async (url, options) => {
      calls.push({ url, options });
      throw new Error('network down');
    },
  });

  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, 'http://127.0.0.1:8002/api/client-events');
  assert.equal(calls[0].options.headers.Authorization, 'Bearer session-token');
  assert.equal(calls[0].options.method, 'POST');
  assert.equal(JSON.parse(calls[0].options.body).event_type, 'rewarded_ad_failed');
});

test('installGlobalClientEventReporting reports unhandled window errors once', async () => {
  const listeners = {};
  const fakeWindow = {
    location: { pathname: '/journal' },
    addEventListener: (type, handler) => {
      listeners[type] = handler;
    },
  };
  const calls = [];

  const cleanup = installGlobalClientEventReporting({
    apiBase: 'http://127.0.0.1:8002',
    getSessionToken: () => 'session-token',
    targetWindow: fakeWindow,
    post: async (url, options) => {
      calls.push({ url, payload: JSON.parse(options.body) });
    },
  });

  await listeners.error({
    message: 'render exploded',
    filename: 'TradingJournal.jsx',
    lineno: 12,
    colno: 34,
    error: new Error('secret-token should not leak'),
  });
  await listeners.error({ message: 'duplicate' });

  assert.equal(typeof cleanup, 'function');
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, 'http://127.0.0.1:8002/api/client-events');
  assert.equal(calls[0].payload.event_type, 'client_unhandled_error');
  assert.equal(calls[0].payload.level, 'error');
  assert.equal(calls[0].payload.message, 'render exploded');
  assert.equal(calls[0].payload.path, '/journal');
  assert.equal(calls[0].payload.details.filename, 'TradingJournal.jsx');
  assert.equal(calls[0].payload.details.lineno, 12);
  assert.doesNotMatch(JSON.stringify(calls[0].payload), /secret-token/);
});

test('installGlobalClientEventReporting reports unhandled promise rejections', async () => {
  const listeners = {};
  const fakeWindow = {
    location: { pathname: '/journal' },
    addEventListener: (type, handler) => {
      listeners[type] = handler;
    },
  };
  const calls = [];

  installGlobalClientEventReporting({
    apiBase: 'http://127.0.0.1:8002',
    getSessionToken: () => '',
    targetWindow: fakeWindow,
    post: async (url, options) => {
      calls.push({ url, payload: JSON.parse(options.body) });
    },
  });

  await listeners.unhandledrejection({
    reason: new Error('network failed'),
  });

  assert.equal(calls.length, 1);
  assert.equal(calls[0].payload.event_type, 'client_unhandled_rejection');
  assert.equal(calls[0].payload.message, 'network failed');
  assert.equal(calls[0].payload.details.reason_name, 'Error');
});

test('getStoredAuthSessionToken reads only the saved session token', () => {
  const storage = {
    getItem: key => key === 'alphamate.devAuth.v1'
      ? JSON.stringify({ session_token: 'session-token', secret: 'ignore-me' })
      : null,
  };

  assert.equal(getStoredAuthSessionToken(storage), 'session-token');
  assert.equal(getStoredAuthSessionToken({ getItem: () => 'not-json' }), '');
  assert.equal(getStoredAuthSessionToken(null), '');
});

test('frontend source avoids direct console error logging', () => {
  const sourceRoot = path.resolve(process.cwd(), 'src');
  const files = [
    path.join(sourceRoot, 'App.jsx'),
    path.join(sourceRoot, 'components', 'StockChart.jsx'),
  ];

  for (const file of files) {
    const source = fs.readFileSync(file, 'utf8');
    assert.doesNotMatch(source, /console\.error/);
  }
});