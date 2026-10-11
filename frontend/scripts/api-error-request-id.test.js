import test from 'node:test';
import assert from 'node:assert/strict';

import {
  appendRequestIdToMessage,
  appendRetryAfterToMessage,
  installAxiosRequestIdMessages,
  requestIdFromAxiosError,
  retryAfterSecondsFromAxiosError,
} from '../src/utils/apiErrorRequestId.js';
import { reviewDisplayFailureMessage } from '../src/utils/reviewDisplayContract.js';

function installedHandlers() {
  const handlers = {};
  installAxiosRequestIdMessages({ interceptors: { response: { use: (fulfilled, rejected) => {
    handlers.fulfilled = fulfilled;
    handlers.rejected = rejected;
  } } } });
  return handlers;
}

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

test('structured 426 detail keeps exact identity code and fixed notice across support headers', async () => {
  const handlers = installedHandlers();
  for (const headers of [undefined, {}, { 'x-request-id': 'request-123' }, { 'retry-after': '15' },
    { 'x-request-id': 'request-123', 'retry-after': '15' },
    { 'x-request-id': 'RAW HEADER INPUT!', 'retry-after': 'RAW RETRY INPUT' }]) {
    const detail = Object.freeze({ code: 'unsupported_review_display_client', message: 'RAW BACKEND INPUT',
      nested: Object.freeze({ values: Object.freeze(['RAW NESTED INPUT']) }) });
    const data = Object.freeze({ detail });
    const error = { response: { status: 426, headers, data } };
    await assert.rejects(() => handlers.rejected(error), rejected => {
      assert.strictEqual(rejected, error);
      assert.strictEqual(rejected.response.data, data);
      assert.strictEqual(rejected.response.data.detail, detail);
      assert.equal(rejected.response.data.detail.code, 'unsupported_review_display_client');
      assert.equal(rejected.response.data.detail.message, 'RAW BACKEND INPUT');
      assert.equal(reviewDisplayFailureMessage(rejected, '고정 실패 안내'), 'AI 복기를 표시하려면 앱을 업데이트해 주세요.');
      return true;
    });
  }
});

test('arbitrary object and array details remain lossless without invoking string coercion', async () => {
  const handlers = installedHandlers();
  for (const detail of [Object.freeze({}), Object.freeze([{ loc: ['body'], msg: 'synthetic validation' }]),
    Object.freeze({ code: 'unknown', message: 'RAW UNKNOWN INPUT', toString: () => assert.fail('detail coercion') })]) {
    const error = { response: { headers: { 'x-request-id': 'request-123', 'retry-after': '10' }, data: Object.freeze({ detail }) } };
    await assert.rejects(() => handlers.rejected(error), rejected => {
      assert.strictEqual(rejected.response.data.detail, detail);
      assert.equal(reviewDisplayFailureMessage(rejected, '고정 실패 안내'), '고정 실패 안내');
      return true;
    });
  }
});

test('string detail decoration retains exact request id retry and deduplication behavior', async () => {
  const handlers = installedHandlers();
  const cases = [
    [{}, '구매 실패', '구매 실패'],
    [{ 'x-request-id': 'request-123' }, '구매 실패', '구매 실패 (문의용 ID: request-123)'],
    [{ 'retry-after': '15' }, '구매 실패', '구매 실패 15초 뒤 다시 시도하세요.'],
    [{ 'x-request-id': 'request-123', 'retry-after': '0' }, '구매 실패', '구매 실패 0초 뒤 다시 시도하세요. (문의용 ID: request-123)'],
    [{ 'x-request-id': 'bad header!', 'retry-after': '999999' }, '구매 실패', '구매 실패'],
    [{ 'x-request-id': 'request-123', 'retry-after': '15' }, '구매 실패 15초 뒤 다시 시도하세요. (문의용 ID: request-123)',
      '구매 실패 15초 뒤 다시 시도하세요. (문의용 ID: request-123)'],
  ];
  for (const [headers, detail, expected] of cases) {
    const error = { response: { headers, data: { detail } } };
    await assert.rejects(() => handlers.rejected(error), rejected => {
      assert.strictEqual(rejected, error);
      assert.equal(rejected.response.data.detail, expected);
      return true;
    });
  }
});

test('null missing and primitive response details keep the existing safe string fallback', async () => {
  const handlers = installedHandlers();
  for (const [detail, expected] of [[null, '요청을 처리하지 못했습니다.'], [undefined, '요청을 처리하지 못했습니다.'],
    ['', '요청을 처리하지 못했습니다.'], [false, '요청을 처리하지 못했습니다.'], [12, '12']]) {
    const error = { response: { data: { detail } } };
    await assert.rejects(() => handlers.rejected(error), rejected => {
      assert.equal(rejected.response.data.detail, expected);
      assert.equal(reviewDisplayFailureMessage(rejected, '고정 실패 안내'), '고정 실패 안내');
      return true;
    });
  }
});

test('null undefined and primitive errors reject the original value without synchronous mutation failure', async () => {
  const handlers = installedHandlers();
  for (const error of [null, undefined, '', 'synthetic network failure', false, true, 0, 42]) {
    let rejected;
    assert.doesNotThrow(() => { rejected = handlers.rejected(error); });
    await rejected.then(() => assert.fail('must reject'), value => assert.strictEqual(value, error));
    assert.equal(reviewDisplayFailureMessage(error, '고정 실패 안내'), '고정 실패 안내');
  }
});

test('network malformed and non Axios object errors keep safe messages and success stays unchanged', async () => {
  const handlers = installedHandlers();
  const response = Object.freeze({ data: 'synthetic success' });
  assert.strictEqual(handlers.fulfilled(response), response);
  for (const error of [new Error('Network Error'), { message: 'Network Error' },
    { message: 'Network Error', response: null }, { message: 'Network Error', response: { data: null } },
    { message: 'Network Error', response: { data: 'synthetic non-JSON' } }]) {
    await assert.rejects(() => handlers.rejected(error), rejected => {
      assert.strictEqual(rejected, error);
      assert.equal(rejected.message, 'Network Error');
      return true;
    });
  }
  for (const error of [{}, { response: {} }]) {
    await assert.rejects(() => handlers.rejected(error), rejected => {
      assert.strictEqual(rejected, error);
      assert.equal(rejected.message, '요청을 처리하지 못했습니다.');
      return true;
    });
  }
});
