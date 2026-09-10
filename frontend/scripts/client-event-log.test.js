import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { performance } from 'node:perf_hooks';
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
      productId: 'basic_review_15',
      purchaseToken: 'secret-purchase-token',
      nested: {
        authorization: 'Bearer secret-session-token',
        safe: 'visible',
      },
    },
  });

  const payloadText = JSON.stringify(payload);
  assert.equal(payload.event_type, 'google_play_purchase_failed');
  assert.equal(payload.details.productId, 'basic_review_15');
  assert.equal(payload.details.nested.safe, 'visible');
  assert.doesNotMatch(payloadText, /secret-purchase-token/);
  assert.doesNotMatch(payloadText, /secret-session-token/);
  assert.match(payloadText, /\[redacted\]/);
});

test('buildClientEventPayload sanitizes credential text without masking metrics', () => {
  const payload = buildClientEventPayload({
    eventType: 'oauth_callback_failed',
    level: 'error',
    message: 'callback?%63ode=SYNTHETIC_ENCODED_CODE&%73tate=SYNTHETIC_ENCODED_STATE&code=SYNTHETIC_DUPLICATE?x=y#fragment status-code=401 error-code=DENIED status_code=401 error_code=DENIED',
    path: '/callback?verification_token=SYNTHETIC_VERIFICATION_TOKEN&shared_token=SYNTHETIC_SHARED_TOKEN',
    details: {
      accessToken: 'SYNTHETIC_ACCESS_TOKEN_DO_NOT_LOG',
      verification_token: 'SYNTHETIC_VERIFICATION_TOKEN_DO_NOT_LOG',
      shared_token: 'SYNTHETIC_SHARED_TOKEN_DO_NOT_LOG',
      'X-AlphaMate-RTDN-Token': 'SYNTHETIC_RTDN_HEADER_DO_NOT_LOG',
      KAKAO_CLIENT_SECRET: 'SYNTHETIC_CLIENT_SECRET_DO_NOT_LOG',
      authorization: 'Bearer SYNTHETIC_AUTHORIZATION_DO_NOT_LOG',
      cookie: 'session=SYNTHETIC_COOKIE_DO_NOT_LOG',
      input_tokens: 123,
      output_tokens: 45,
      status_code: 401,
      error_code: 'OAUTH_CALLBACK_FAILED',
      'status-code': 401,
      'error-code': 'DENIED',
      note: String.raw`payload={\"verification_token\":\"SYNTHETIC_ESCAPED\\\"VALUE&x=y?#fragment\"}`,
    },
  });

  const payloadText = JSON.stringify(payload);
  assert.doesNotMatch(payloadText, /SYNTHETIC_/);
  assert.match(payloadText, /\[redacted\]/);
  assert.equal(payload.details.input_tokens, 123);
  assert.equal(payload.details.output_tokens, 45);
  assert.equal(payload.details.status_code, 401);
  assert.equal(payload.details.error_code, 'OAUTH_CALLBACK_FAILED');
  assert.equal(payload.details['status-code'], 401);
  assert.equal(payload.details['error-code'], 'DENIED');
  assert.match(payload.message, /status-code=401/);
  assert.match(payload.message, /error-code=DENIED/);
  assert.match(payload.message, /status_code=401/);
  assert.match(payload.message, /error_code=DENIED/);
});

test('buildClientEventPayload bounds adversarial message and detail sanitization', () => {
  const sizes = [1000, 2000, 4000, 16000];
  const elapsed = [];

  for (const size of sizes) {
    const longValue = '-'.repeat(size);
    const startedAt = performance.now();
    const payload = buildClientEventPayload({
      message: longValue,
      details: {
        dots: '.'.repeat(size),
        mixed: 'alpha-._'.repeat(Math.ceil(size / 8)).slice(0, size),
        multiline: 'Cookie: SYNTHETIC_HEADER_VALUE\n'.repeat(Math.ceil(size / 31)),
      },
    });
    elapsed.push((performance.now() - startedAt) / 1000);
    assert.ok(payload.message.length <= 500);
    assert.ok(payload.details.dots.length <= 1000);
    assert.ok(payload.details.mixed.length <= 1000);
    assert.ok(payload.details.multiline.length <= 1000);
    assert.doesNotMatch(payload.details.multiline, /SYNTHETIC_/);
    assert.match(payload.message, /\[truncated\]$/);
  }

  assert.ok(elapsed[2] < 0.35, `4000-character input took ${elapsed[2]}s`);
  assert.ok(elapsed[3] < 1.0, `16000-character input took ${elapsed[3]}s`);
  assert.ok(
    elapsed[3] < Math.max(0.10, elapsed[0] * 64),
    `adversarial scaling was ${elapsed[3] / elapsed[0]}x`,
  );
});

test('buildClientEventPayload redacts a credential crossing the truncation boundary', () => {
  const message = `${'x'.repeat(465)} {\\"verification_token\\":\\"SYNTHETIC_BOUNDARY_SECRET_DO_NOT_LOG`;
  const payload = buildClientEventPayload({ message, details: { note: message.repeat(3) } });
  const payloadText = JSON.stringify(payload);

  assert.doesNotMatch(payloadText, /SYNTHETIC_/);
  assert.match(payloadText, /\[redacted\]/);
  assert.match(payload.message, /\[truncated\]$/);
  assert.ok(payload.message.length <= 500);
  assert.ok(payload.details.note.length <= 1000);
});

test('buildClientEventPayload fails closed for multiline quoted credentials beyond the limit', () => {
  const inputs = [
    `${'x'.repeat(300)} private_key="SYNTHETIC_FIRST_LINE\nSYNTHETIC_SECOND_LINE${'y'.repeat(1000)}"`,
    `${'x'.repeat(300)} {\\"verification_token\\":\\"SYNTHETIC_FIRST_LINE\nSYNTHETIC_SECOND_LINE${'y'.repeat(1000)}\\"}`,
  ];

  for (const raw of inputs) {
    const original = raw.slice();
    const payload = buildClientEventPayload({ message: raw, details: { note: raw } });
    const payloadText = JSON.stringify(payload);
    assert.equal(raw, original);
    assert.doesNotMatch(payloadText, /SYNTHETIC_/);
    assert.match(payloadText, /\[redacted\]/);
    assert.match(payload.message, /\[truncated\]$/);
    assert.match(payload.details.note, /\[truncated\]$/);
  }
});

test('buildClientEventPayload keeps truncation boundaries credential-safe', () => {
  const limit = 500;
  const secret = 'SYNTHETIC_BOUNDARY_SECRET_DO_NOT_LOG';
  const nearLimit = (suffix, visibleSuffix) => `${'x'.repeat(Math.max(0, limit - visibleSuffix))}${suffix}`;
  const inputs = {
    keyStart: nearLimit(` private_key=${secret}`, 5),
    encodedKeyCrossing: nearLimit(` %63ode=${secret}`, 3),
    betweenKeyAndEqual: nearLimit(` private_key   =${secret}`, 14),
    immediatelyAfterEqual: nearLimit(` private_key=${secret}`, 13),
    quotedValueStart: nearLimit(` private_key="${secret}"`, 15),
    valueMiddle: nearLimit(` private_key="${secret}"`, 36),
    escapedQuote: nearLimit(` private_key="AA\\\"${secret}"`, 46),
    escapedBackslash: nearLimit(` private_key="AA\\\\${secret}"`, 46),
    beforeLf: nearLimit(` private_key="AA\n${secret}"`, 28),
    afterCrlf: nearLimit(` private_key="AA\r\n${secret}"`, 30),
    multiline: nearLimit(` private_key="AA\n${secret}${'z'.repeat(600)}"`, 48),
    duplicateQuery: nearLimit(` code=${secret}&code=${secret}`, 48),
    longBenignPrefix: `${'benign '.repeat(100)} private_key="${secret}"`,
    emptyValue: nearLimit(' verification_token=', 24),
    danglingBackslash: nearLimit(' verification_token=\\', 25),
    malformedPercentValue: nearLimit(' code=%GZ', 12),
    trailingCr: nearLimit(' Cookie: value\r', 15),
    trailingLf: nearLimit(' Cookie: value\n', 15),
    controlCharacter: nearLimit(` code=${secret}\x00tail`, 48),
  };

  for (const [label, raw] of Object.entries(inputs)) {
    const original = raw.slice();
    const safe = buildClientEventPayload({ message: raw }).message;
    assert.equal(raw, original, label);
    assert.ok(safe.length <= limit, label);
    assert.doesNotMatch(safe, /SYNTHETIC_/, label);
  }
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
  const credentialShapedToken = 'code=SYNTHETIC_SESSION_VALUE?part=a&part=b#fragment';
  const storage = {
    getItem: key => key === 'alphamate.devAuth.v1'
      ? JSON.stringify({ session_token: credentialShapedToken, secret: 'ignore-me' })
      : null,
  };

  assert.equal(getStoredAuthSessionToken(storage), credentialShapedToken);
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
