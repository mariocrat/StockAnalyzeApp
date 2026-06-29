import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';
import { spawnSync } from 'node:child_process';

import { formatOwnerFrontendReleaseReport, releaseEnvFromProcess, validateReleaseEnv } from './validate-release-env.js';

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

test('frontend env example documents release check settings', () => {
  const example = fs.readFileSync(path.resolve(process.cwd(), '.env.example'), 'utf8');
  const requiredKeys = [
    'VITE_ALPHAMATE_ENV',
    'VITE_APP_NAME',
    'VITE_ENABLE_DEV_TOOLS',
    'VITE_API_BASE',
    'VITE_ADMOB_REWARDED_AD_UNIT_ID',
    'VITE_ADMOB_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT_ID',
    'VITE_GOOGLE_PLAY_PACKAGE_NAME',
    'ALPHAMATE_ANDROID_KEYSTORE_FILE',
    'ALPHAMATE_ANDROID_KEYSTORE_PASSWORD',
    'ALPHAMATE_ANDROID_KEY_ALIAS',
    'ALPHAMATE_ANDROID_KEY_PASSWORD',
    'ALPHAMATE_ANDROID_VERSION_CODE',
    'ALPHAMATE_ANDROID_VERSION_NAME',
  ];

  for (const key of requiredKeys) {
    assert.match(example, new RegExp(`(^|\\n)#?\\s*${key}=`), `${key} should be documented in frontend/.env.example`);
  }
});

test('frontend release env template is production focused', () => {
  const template = fs.readFileSync(path.resolve(process.cwd(), '.env.release.example'), 'utf8');
  const requiredKeys = [
    'VITE_ALPHAMATE_ENV=production',
    'VITE_APP_NAME',
    'VITE_ENABLE_DEV_TOOLS=false',
    'VITE_API_BASE',
    'VITE_KAKAO_REST_API_KEY',
    'VITE_KAKAO_REDIRECT_URI',
    'VITE_NAVER_CLIENT_ID',
    'VITE_NAVER_REDIRECT_URI',
    'VITE_ADMOB_REWARDED_AD_UNIT_ID',
    'VITE_ADMOB_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT_ID',
    'VITE_GOOGLE_PLAY_PACKAGE_NAME',
    'ALPHAMATE_ANDROID_VERSION_CODE',
    'ALPHAMATE_ANDROID_VERSION_NAME',
    'ALPHAMATE_ANDROID_KEYSTORE_FILE',
    'ALPHAMATE_ANDROID_KEYSTORE_PASSWORD',
    'ALPHAMATE_ANDROID_KEY_ALIAS',
    'ALPHAMATE_ANDROID_KEY_PASSWORD',
  ];

  for (const key of requiredKeys) {
    assert.match(template, new RegExp(`(^|\\n)#?\\s*${key}`), `${key} should be documented in frontend/.env.release.example`);
  }
  assert.doesNotMatch(template, /VITE_DEV_/);
  assert.doesNotMatch(template, /dev-token/);
});

test('release env loader accepts an explicit frontend env file', () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'alphamate-frontend-env-'));
  const envPath = path.join(tempDir, '.env.release');
  fs.writeFileSync(envPath, [
    'VITE_APP_NAME=ReleaseFileAlphaMate',
    'VITE_ALPHAMATE_ENV=production',
  ].join('\n'));

  const previousEnvFile = process.env.ALPHAMATE_FRONTEND_ENV_FILE;
  const previousAppName = process.env.VITE_APP_NAME;
  const previousAppEnv = process.env.VITE_ALPHAMATE_ENV;
  try {
    process.env.ALPHAMATE_FRONTEND_ENV_FILE = envPath;
    delete process.env.VITE_APP_NAME;
    delete process.env.VITE_ALPHAMATE_ENV;

    const env = releaseEnvFromProcess();

    assert.equal(env.VITE_APP_NAME, 'ReleaseFileAlphaMate');
    assert.equal(env.VITE_ALPHAMATE_ENV, 'production');
  } finally {
    if (previousEnvFile === undefined) delete process.env.ALPHAMATE_FRONTEND_ENV_FILE;
    else process.env.ALPHAMATE_FRONTEND_ENV_FILE = previousEnvFile;
    if (previousAppName === undefined) delete process.env.VITE_APP_NAME;
    else process.env.VITE_APP_NAME = previousAppName;
    if (previousAppEnv === undefined) delete process.env.VITE_ALPHAMATE_ENV;
    else process.env.VITE_ALPHAMATE_ENV = previousAppEnv;
  }
});

test('formats owner frontend release report without exposing secret values', () => {
  const result = validateReleaseEnv(validReleaseEnv({
    VITE_ALPHAMATE_ENV: 'development',
    VITE_API_BASE: 'http://127.0.0.1:8002',
    VITE_ADMOB_REWARDED_AD_UNIT_ID: 'ca-app-pub-3940256099942544/5224354917',
    ALPHAMATE_ANDROID_KEYSTORE_PASSWORD: 'never-print-this-keystore-password',
    ALPHAMATE_ANDROID_KEY_PASSWORD: 'never-print-this-key-password',
  }));

  const report = formatOwnerFrontendReleaseReport(result, {
    VITE_APP_NAME: 'AlphaMate',
    VITE_GOOGLE_PLAY_PACKAGE_NAME: 'com.mariocrat.stockanalyze',
  });

  assert.match(report, /프론트\/앱 출시 준비 보고서/);
  assert.match(report, /전체 상태: 준비 필요/);
  assert.match(report, /준비율: \d\/8 \(\d+%\)/);
  assert.match(report, /앱 이름: AlphaMate/);
  assert.match(report, /구글 플레이 패키지: com\.mariocrat\.stockanalyze/);
  assert.match(report, /다음에 할 일/);
  assert.match(report, /운영 모드로 바꾸기/);
  assert.match(report, /API 서버 주소를 운영 HTTPS 주소로 바꾸기/);
  assert.match(report, /AdMob 운영 광고 단위로 바꾸기/);
  assert.equal(report.match(/API 서버 주소를 운영 HTTPS 주소로 바꾸기/g).length, 1);
  assert.match(report, /VITE_ALPHAMATE_ENV/);
  assert.doesNotMatch(report, /never-print-this/);
});

test('owner frontend release report CLI prints report and hides secret values', () => {
  const script = path.resolve(process.cwd(), 'scripts/owner-release-report.js');
  const env = validReleaseEnv({
    ALPHAMATE_ANDROID_KEYSTORE_PASSWORD: 'never-print-cli-keystore-password',
    ALPHAMATE_ANDROID_KEY_PASSWORD: 'never-print-cli-key-password',
  });
  const result = spawnSync(process.execPath, [script], {
    cwd: process.cwd(),
    env: { ...process.env, ...env },
    encoding: 'utf8',
  });

  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /프론트\/앱 출시 준비 보고서/);
  assert.match(result.stdout, /전체 상태: 준비됨/);
  assert.doesNotMatch(result.stdout, /never-print-cli/);
});

test('package script exposes owner release report command', () => {
  const pkg = JSON.parse(fs.readFileSync(path.resolve(process.cwd(), 'package.json'), 'utf8'));

  assert.equal(pkg.scripts['release:report'], 'node scripts/owner-release-report.js');
});
