import test from 'node:test';
import assert from 'node:assert/strict';

import { parseOAuthAppReturnUrl } from '../src/utils/oauthAppReturn.js';

test('parses package scheme OAuth app return ticket without exposing provider tokens', () => {
  const parsed = parseOAuthAppReturnUrl(
    'com.mariocrat.stockanalyze://oauth/kakao?ticket=one-time-ticket&state=state-123',
  );

  assert.deepEqual(parsed, {
    provider: 'kakao',
    ticket: 'one-time-ticket',
    state: 'state-123',
    error: '',
  });
});

test('ignores unsupported OAuth app return URLs', () => {
  assert.equal(parseOAuthAppReturnUrl('https://api.alphamate.kr/api/auth/kakao/callback?code=x'), null);
  assert.equal(parseOAuthAppReturnUrl('com.mariocrat.stockanalyze://oauth/other?ticket=x'), null);
  assert.equal(parseOAuthAppReturnUrl('not-a-url'), null);
});
