import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import { setImmediate as nextTurn } from 'node:timers/promises';

const source = readFileSync(new URL('../src/components/TradingJournal.jsx', import.meta.url), 'utf8');
// Execute the actual handlers with network/storage doubles; no provider or API calls.
function handler(name) {
  const start = source.indexOf(`  const ${name} = `);
  assert.ok(start >= 0, name);
  return source.slice(start, source.indexOf('\n  };', start) + 5);
}

function harness({ provider = 'naver', scheme = 'com.mariocrat.stockanalyze.debug', devToken = '', logoutFails = false } = {}) {
  const storage = new Map([['auth', 'old-session'], ['state', 'old-state']]);
  const requests = [];
  const opened = [];
  const state = { loading: false, session: { session_token: 'old-token' }, entitlements: { plan: 'pro' } };
  const entitlementWrites = [];
  const pendingEntitlements = [];
  const authSessionGenerationRef = { current: 0 };
  const context = {
    URL, Date, JSON, apiBase: 'https://sanitized.invalid',
    AUTH_STORAGE_KEY: 'auth', OAUTH_STATE_KEY: 'state',
    DEV_AUTH_TOKEN: devToken, DEV_ACCESS_PLAN: 'free', DEV_ENTITLEMENT_TOKEN: '',
    activeAuthToken: 'old-token', authSession: state.session,
    ANDROID_OAUTH_APP_SCHEME: scheme, OAUTH_APP_SCHEME_STATE_MARKER: '|stockboda-app-scheme=',
    KAKAO_REST_API_KEY: 'synthetic-kakao', NAVER_CLIENT_ID: 'synthetic-naver',
    localStorage: { getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) },
    setAuthLoading: value => { state.loading = value; },
    authSessionGenerationRef,
    setAuthSessionState: value => { state.session = value; },
    setEntitlements: value => { state.entitlements = value; entitlementWrites.push(value); },
    setDataSummary: () => {}, resetJournalWorkspace: () => {}, setMessage: () => {},
    onEntitlementsChange: () => {}, loadDataSummary: async () => {},
    oauthConfigured: () => true, oauthServerReady: () => true,
    oauthRedirectUri: () => 'https://sanitized.invalid/callback',
    randomState: () => 'fresh-nonce',
    loadStoredOAuthState: () => JSON.parse(storage.get('state') || 'null'),
    Capacitor: { isNativePlatform: () => true },
    Browser: { open: async ({ url }) => { opened.push(new URL(url)); } },
    window: { location: { href: 'https://localhost/' }, history: { replaceState: () => {} } },
    reportJournalClientEvent: () => {},
    axios: {
      post: async (url, body, config) => {
        requests.push({ url, body, config });
        if (url.endsWith('/logout') && logoutFails) throw new Error('offline');
        return { data: { session_token: 'new-token', user: { provider } } };
      },
      get: (url, config) => {
        requests.push({ url, config });
        // Keep the old or development request pending until the test chooses its outcome.
        if (config.headers.Authorization !== 'Bearer new-token') {
          return new Promise((resolve, reject) => pendingEntitlements.push({ resolve, reject }));
        }
        return Promise.resolve({ data: { plan: 'pro', owner: provider } });
      },
    },
  };
  const functions = runInNewContext(
    ['setAuthSession', 'loadEntitlements', 'handleLogout', 'handleOAuthStart', 'finishOAuthTicketLogin'].map(handler).join('\n')
      + '\n({ handleLogout, handleOAuthStart, finishOAuthTicketLogin })', context,
  );
  const disabled = () => runInNewContext(
    source.match(new RegExp(`disabled=\\{(authLoading \\|\\| !oauthConfigured\\('${provider}'\\))\\}`))[1],
    { authLoading: state.loading, oauthConfigured: context.oauthConfigured },
  );
  return { state, storage, requests, opened, entitlementWrites, pendingEntitlements, functions, disabled };
}

async function finishSameProviderLogin(h, provider, scheme) {
  await h.functions.handleOAuthStart(provider);
  const pending = JSON.parse(h.storage.get('state'));
  assert.equal(pending.provider, provider);
  assert.ok(pending.state.endsWith(scheme));
  assert.equal(h.opened[0].hostname, provider === 'kakao' ? 'kauth.kakao.com' : 'nid.naver.com');
  await h.functions.finishOAuthTicketLogin({ provider, ticket: 'synthetic-new-ticket', state: pending.state });
  assert.equal(h.state.session.session_token, 'new-token');
  assert.equal(h.state.loading, false);
  assert.equal(h.storage.has('state'), false);
}

async function verifyRelogin(provider, scheme) {
  const h = harness({ provider, scheme });
  const logout = h.functions.handleLogout();
  await nextTurn();
  assert.equal(h.state.session, null);
  assert.equal(h.disabled(), false, 'login must not wait for revoked-token entitlements');
  await logout;
  assert.equal(h.state.entitlements, null);
  assert.equal(h.storage.has('auth'), false);
  assert.equal(h.storage.has('state'), false);
  assert.equal(h.requests.length, 1, 'only logout; no stale entitlement request');
  await finishSameProviderLogin(h, provider, scheme);
}

test('kakao release scheme: logout enables login and accepts a fresh same-provider ticket', async () => {
  await verifyRelogin('kakao', 'com.mariocrat.stockanalyze');
});
test('kakao Debug scheme: logout enables login and accepts a fresh same-provider ticket', async () => {
  await verifyRelogin('kakao', 'com.mariocrat.stockanalyze.debug');
});
test('naver release scheme: logout enables login and accepts a fresh same-provider ticket', async () => {
  await verifyRelogin('naver', 'com.mariocrat.stockanalyze');
});
test('naver Debug scheme: logout enables login and accepts a fresh same-provider ticket', async () => {
  await verifyRelogin('naver', 'com.mariocrat.stockanalyze.debug');
});

test('failed logout request still releases local login controls', async () => {
  const h = harness({ logoutFails: true });
  const logout = h.functions.handleLogout();
  await nextTurn();
  assert.equal(h.disabled(), false);
  await logout;
  assert.equal(h.state.session, null);
});

test('slow development entitlement refresh does not hold the auth loading flag', async t => {
  for (const provider of ['kakao', 'naver']) {
    for (const outcome of ['success', 'failure']) {
      await t.test(`${provider}: late development entitlement ${outcome} cannot overwrite the new session`, async () => {
        const h = harness({ provider, devToken: 'dev-token' });
        const logout = h.functions.handleLogout();
        await nextTurn();
        assert.equal(h.disabled(), false);
        await logout;
        assert.equal(h.state.session, null);
        assert.equal(h.pendingEntitlements.length, 1);
        assert.equal(h.requests.at(-1).config.headers.Authorization, 'Bearer dev-token');

        await finishSameProviderLogin(h, provider, 'com.mariocrat.stockanalyze.debug');
        assert.deepEqual(h.state.entitlements, { plan: 'pro', owner: provider });
        const writesAfterLogin = h.entitlementWrites.length;
        const oldRequest = h.pendingEntitlements[0];
        if (outcome === 'success') oldRequest.resolve({ data: { plan: 'free', owner: 'dev' } });
        else oldRequest.reject(new Error('synthetic delayed failure'));
        await nextTurn();

        assert.deepEqual(h.state.entitlements, { plan: 'pro', owner: provider });
        assert.equal(h.entitlementWrites.length, writesAfterLogin, 'stale request must not write entitlement state');
      });
    }
  }
});
