import test from 'node:test';
import assert from 'node:assert/strict';

import { validateReleaseEnv } from './validate-release-env.js';

test('rejects localhost API and enabled dev tools for release builds', () => {
  const result = validateReleaseEnv({
    VITE_ALPHAMATE_ENV: 'production',
    VITE_ENABLE_DEV_TOOLS: 'true',
    VITE_API_BASE: 'http://127.0.0.1:8002',
    VITE_ADMOB_REWARDED_AD_UNIT_ID: 'ca-app-pub-3940256099942544/5224354917',
    VITE_GOOGLE_PLAY_PACKAGE_NAME: '',
  });

  assert.equal(result.ok, false);
  assert.match(result.errors.join('\n'), /VITE_ENABLE_DEV_TOOLS/);
  assert.match(result.errors.join('\n'), /VITE_API_BASE/);
  assert.match(result.errors.join('\n'), /VITE_ADMOB_REWARDED_AD_UNIT_ID/);
  assert.match(result.errors.join('\n'), /VITE_GOOGLE_PLAY_PACKAGE_NAME/);
});

test('accepts production release settings without exposing secret requirements', () => {
  const result = validateReleaseEnv({
    VITE_ALPHAMATE_ENV: 'production',
    VITE_ENABLE_DEV_TOOLS: 'false',
    VITE_API_BASE: 'https://api.example.com',
    VITE_ADMOB_REWARDED_AD_UNIT_ID: 'ca-app-pub-1234567890123456/9876543210',
    VITE_GOOGLE_PLAY_PACKAGE_NAME: 'com.mariocrat.stockanalyze',
  });

  assert.equal(result.ok, true);
  assert.deepEqual(result.errors, []);
});
