import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import { parseOAuthAppReturnUrl } from '../src/utils/oauthAppReturn.js';

const journalSource = readFileSync(new URL('../src/components/TradingJournal.jsx', import.meta.url), 'utf8');

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

test('native OAuth uses an in-app browser and closes it after the app callback', () => {
  assert.match(journalSource, /Capacitor\.isNativePlatform\(\)/);
  assert.match(journalSource, /Browser\.open\(\{ url: authUrl\.toString\(\) \}\)/);
  assert.match(journalSource, /Browser\.close\(\)\.catch\(\(\) => \{\}\)/);
});
