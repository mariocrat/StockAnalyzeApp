import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import { validateReleaseEnv } from './validate-release-env.js';

function validReleaseEnv(overrides = {}) {
  const keystoreFile = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'alphamate-release-')), 'upload.jks');
  fs.writeFileSync(keystoreFile, 'test keystore placeholder');
  return {
    VITE_ALPHAMATE_ENV: 'production',
    VITE_APP_NAME: 'AlphaMate',
    VITE_ENABLE_DEV_TOOLS: 'false',
    VITE_API_BASE: 'https://api.example.com',
    VITE_ADMOB_REWARDED_AD_UNIT_ID: 'ca-app-pub-1234567890123456/9876543210',
    VITE_ADMOB_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT_ID: 'ca-app-pub-1234567890123456/1234567890',
    VITE_GOOGLE_PLAY_PACKAGE_NAME: 'com.mariocrat.stockanalyze',
    ALPHAMATE_ANDROID_KEYSTORE_FILE: keystoreFile,
    ALPHAMATE_ANDROID_KEYSTORE_PASSWORD: 'keystore-password',
    ALPHAMATE_ANDROID_KEY_ALIAS: 'alphamate-upload',
    ALPHAMATE_ANDROID_KEY_PASSWORD: 'key-password',
    ALPHAMATE_ANDROID_VERSION_CODE: '1',
    ALPHAMATE_ANDROID_VERSION_NAME: '1.0.0',
    ...overrides,
  };
}

test('rejects localhost API and enabled dev tools for release builds', () => {
  const result = validateReleaseEnv({
    VITE_ALPHAMATE_ENV: 'production',
    VITE_ENABLE_DEV_TOOLS: 'true',
    VITE_API_BASE: 'http://127.0.0.1:8002',
    VITE_ADMOB_REWARDED_AD_UNIT_ID: 'ca-app-pub-3940256099942544/5224354917',
    VITE_ADMOB_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT_ID: 'ca-app-pub-3940256099942544/1033173712',
    VITE_GOOGLE_PLAY_PACKAGE_NAME: '',
  });

  assert.equal(result.ok, false);
  assert.match(result.errors.join('\n'), /VITE_ENABLE_DEV_TOOLS/);
  assert.match(result.errors.join('\n'), /VITE_API_BASE/);
  assert.match(result.errors.join('\n'), /VITE_ADMOB_REWARDED_AD_UNIT_ID/);
  assert.match(result.errors.join('\n'), /VITE_ADMOB_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT_ID/);
  assert.match(result.errors.join('\n'), /VITE_GOOGLE_PLAY_PACKAGE_NAME/);
});

test('accepts production release settings without exposing secret requirements', () => {
  const result = validateReleaseEnv(validReleaseEnv());

  assert.equal(result.ok, true);
  assert.deepEqual(result.errors, []);
});

test('requires Android signing settings for release builds', () => {
  const result = validateReleaseEnv(validReleaseEnv({
    ALPHAMATE_ANDROID_KEYSTORE_FILE: '',
    ALPHAMATE_ANDROID_KEYSTORE_PASSWORD: '',
    ALPHAMATE_ANDROID_KEY_ALIAS: '',
    ALPHAMATE_ANDROID_KEY_PASSWORD: '',
  }));

  assert.equal(result.ok, false);
  assert.match(result.errors.join('\n'), /ALPHAMATE_ANDROID_KEYSTORE_FILE/);
  assert.match(result.errors.join('\n'), /ALPHAMATE_ANDROID_KEYSTORE_PASSWORD/);
  assert.match(result.errors.join('\n'), /ALPHAMATE_ANDROID_KEY_ALIAS/);
  assert.match(result.errors.join('\n'), /ALPHAMATE_ANDROID_KEY_PASSWORD/);
});

test('requires valid Android version settings for release builds', () => {
  const result = validateReleaseEnv(validReleaseEnv({
    ALPHAMATE_ANDROID_VERSION_CODE: '0',
    ALPHAMATE_ANDROID_VERSION_NAME: 'version-one',
  }));

  assert.equal(result.ok, false);
  assert.match(result.errors.join('\n'), /ALPHAMATE_ANDROID_VERSION_CODE/);
  assert.match(result.errors.join('\n'), /ALPHAMATE_ANDROID_VERSION_NAME/);
});

test('rejects missing Android keystore file for release builds', () => {
  const result = validateReleaseEnv(validReleaseEnv({
    ALPHAMATE_ANDROID_KEYSTORE_FILE: 'D:/secure/missing-upload-key.jks',
  }));

  assert.equal(result.ok, false);
  assert.match(result.errors.join('\n'), /ALPHAMATE_ANDROID_KEYSTORE_FILE/);
  assert.match(result.errors.join('\n'), /does not exist/);
});
