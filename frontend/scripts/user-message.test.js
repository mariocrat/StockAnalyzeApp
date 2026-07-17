import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { toKoreanUserMessage } from '../src/utils/userMessage.js';

const appSource = readFileSync(fileURLToPath(new URL('../src/App.jsx', import.meta.url)), 'utf8');

test('converts raw AdMob publisher errors into a Korean user message', () => {
  const message = toKoreanUserMessage(
    'Publisher data not found. <https://support.google.com/admob/answer/9905175#9>',
  );

  assert.equal(message, '광고를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.');
  assert.doesNotMatch(message, /https?:|Publisher|AdMob/i);
});

test('keeps clear Korean notices while removing technical URLs', () => {
  const message = toKoreanUserMessage('광고 보상을 확인 중입니다. https://internal.example/error');

  assert.equal(message, '광고 보상을 확인 중입니다.');
});

test('removes support request identifiers from Korean user notices', () => {
  const message = toKoreanUserMessage('요청을 처리하지 못했습니다. (문의용 ID: abc12345)');

  assert.equal(message, '요청을 처리하지 못했습니다.');
});

test('replaces unknown English errors with a safe Korean fallback', () => {
  const message = toKoreanUserMessage('Something unexpected happened in SDK layer');

  assert.equal(message, '요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.');
});

test('localizes advanced review access errors', () => {
  const message = toKoreanUserMessage('Advanced review ticket required.');

  assert.equal(message, '심화 복기 이용권이 필요합니다. 이용권을 확인해 주세요.');
});

test('keeps deliberate Korean debug guidance even when it names AdMob', () => {
  const source = '테스트 광고는 실제 이용권을 지급하지 않습니다. 실제 AdMob 설정이 필요합니다.';

  assert.equal(toKoreanUserMessage(source), source);
});

test('shows app-level failures in a Korean popup instead of inline technical text', () => {
  assert.match(appSource, /className="journal-notice-backdrop"/);
  assert.match(appSource, /<h3 id="app-notice-title">안내<\/h3>/);
  assert.match(appSource, /자동으로 다시 확인하는 중입니다\./);
  assert.doesNotMatch(appSource, /\$\{s\.name\} No data/);
});
