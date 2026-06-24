import test from 'node:test';
import assert from 'node:assert/strict';

import {
  appendRequestIdToMessage,
  appendRetryAfterToMessage,
  installAxiosRequestIdMessages,
  requestIdFromAxiosError,
  retryAfterSecondsFromAxiosError,
} from '../src/utils/apiErrorRequestId.js';

test('appendRequestIdToMessage adds a short support id once', () => {
  const message = appendRequestIdToMessage('AI 분석을 불러오지 못했습니다.', 'request-123_ABC');

  assert.equal(message, 'AI 분석을 불러오지 못했습니다. (문의용 ID: request-123_ABC)');
  assert.equal(appendRequestIdToMessage(message, 'request-123_ABC'), message);
});

test('requestIdFromAxiosError reads response headers case-insensitively', () => {
  assert.equal(
    requestIdFromAxiosError({
      response: { headers: { 'x-request-id': 'request-lower' } },
    }),
    'request-lower',
  );
  assert.equal(
    requestIdFromAxiosError({
      response: { headers: { 'X-Request-ID': 'request-upper' } },
    }),
    'request-upper',
  );
  assert.equal(
    requestIdFromAxiosError({
      response: { headers: { get: key => (key === 'x-request-id' ? 'request-getter' : '') } },
    }),
    'request-getter',
  );
});

test('requestIdFromAxiosError ignores unsafe or oversized request ids', () => {
  assert.equal(
    requestIdFromAxiosError({
      response: { headers: { 'x-request-id': 'bad id with spaces!' } },
    }),
    '',
  );
  assert.equal(
    requestIdFromAxiosError({
      response: { headers: { 'x-request-id': 'x'.repeat(200) } },
    }),
    '',
  );
});

test('retryAfterSecondsFromAxiosError reads safe retry-after values', () => {
  assert.equal(
    retryAfterSecondsFromAxiosError({
      response: { headers: { 'retry-after': '12' } },
    }),
    12,
  );
  assert.equal(
    retryAfterSecondsFromAxiosError({
      response: { headers: { 'Retry-After': '0' } },
    }),
    0,
  );
  assert.equal(
    retryAfterSecondsFromAxiosError({
      response: { headers: { 'Retry-After': '999999' } },
    }),
    null,
  );
});

test('appendRetryAfterToMessage explains when the user can retry once', () => {
  const message = appendRetryAfterToMessage('AI 분석 요청이 많습니다.', 15);

  assert.equal(message, 'AI 분석 요청이 많습니다. 15초 뒤 다시 시도하세요.');
  assert.equal(appendRetryAfterToMessage(message, 15), message);
  assert.equal(appendRetryAfterToMessage('AI 분석 요청이 많습니다.', null), 'AI 분석 요청이 많습니다.');
});

test('installAxiosRequestIdMessages appends request id to axios error detail', async () => {
  const handlers = {};
  const fakeAxios = {
    interceptors: {
      response: {
        use: (onFulfilled, onRejected) => {
          handlers.onFulfilled = onFulfilled;
          handlers.onRejected = onRejected;
        },
      },
    },
  };
  installAxiosRequestIdMessages(fakeAxios);

  const error = {
    response: {
      headers: { 'x-request-id': 'request-123' },
      data: { detail: '구매를 완료하지 못했습니다.' },
    },
  };

  await assert.rejects(
    () => handlers.onRejected(error),
    rejected => {
      assert.equal(
        rejected.response.data.detail,
        '구매를 완료하지 못했습니다. (문의용 ID: request-123)',
      );
      return true;
    },
  );
});
