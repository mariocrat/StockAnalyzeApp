import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';

const source = readFileSync(new URL('../src/components/TradingJournal.jsx', import.meta.url), 'utf8');
const readiness = source.slice(source.indexOf('  const oauthPublicConfigured ='), source.indexOf('  const oauthDisabledReason ='));
test('Debug scheme guard rejects each missing public OAuth setting', () => {
  const config = readFileSync(new URL('../vite.config.js', import.meta.url), 'utf8');
  const start = config.indexOf('  if (env.VITE_ANDROID_OAUTH_APP_SCHEME');
  const end = config.indexOf('  const appName', start);
  assert.ok(start >= 0 && end > start, 'Debug scheme guard');
  const guard = config.slice(start, end);
  const required = ['VITE_KAKAO_REST_API_KEY', 'VITE_NAVER_CLIENT_ID', 'VITE_KAKAO_REDIRECT_URI', 'VITE_NAVER_REDIRECT_URI'];
  const env = Object.fromEntries(required.map(key => [key, 'synthetic']));
  env.VITE_ANDROID_OAUTH_APP_SCHEME = 'com.mariocrat.stockanalyze.debug';
  assert.doesNotThrow(() => runInNewContext(guard, { env }));
  for (const key of required) {
    env[key] = ' ';
    assert.throws(() => runInNewContext(guard, { env }), new RegExp(key));
    env[key] = 'synthetic';
  }
  env.VITE_ANDROID_OAUTH_APP_SCHEME = 'com.mariocrat.stockanalyze';
  for (const key of required) env[key] = '';
  assert.doesNotThrow(() => runInNewContext(guard, { env }));
});

function verifyInitialLogin(provider) {
  for (const status of [null, { providers: { [provider]: { server_ready: true } } }]) {
    const context = { KAKAO_REST_API_KEY: 'synthetic', NAVER_CLIENT_ID: 'synthetic', oauthServerStatus: status };
    const configured = runInNewContext(readiness + `\noauthConfigured('${provider}')`, context);
    assert.equal(configured, true);
    const match = source.match(new RegExp(`disabled=\\{(authLoading \\|\\| !oauthConfigured\\('${provider}'\\))\\}`));
    assert.ok(match, `${provider} login button condition`);
    for (const loading of [false, true, false]) {
      assert.equal(runInNewContext(match[1], { authLoading: loading, oauthConfigured: () => configured }), loading);
    }
  }
}

function verifyMissingPublicKey(provider) {
  assert.equal(runInNewContext(readiness + `\noauthConfigured('${provider}')`, {
    KAKAO_REST_API_KEY: '', NAVER_CLIENT_ID: '',
    oauthServerStatus: { providers: { [provider]: { server_ready: true } } },
  }), false);
}

test('kakao: public config enables fresh login independently of server fetch timing', () => verifyInitialLogin('kakao'));
test('naver: public config enables fresh login independently of server fetch timing', () => verifyInitialLogin('naver'));
test('kakao: ready server cannot compensate for missing packaged public credentials', () => verifyMissingPublicKey('kakao'));
test('naver: ready server cannot compensate for missing packaged public credentials', () => verifyMissingPublicKey('naver'));
