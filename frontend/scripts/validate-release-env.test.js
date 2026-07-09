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
    VITE_API_BASE: 'https://api.alphamate.kr',
    VITE_KAKAO_REST_API_KEY: 'kakao-rest-api-key',
    VITE_KAKAO_REDIRECT_URI: 'https://api.alphamate.kr/api/auth/kakao/callback',
    VITE_NAVER_CLIENT_ID: 'naver-client-id',
    VITE_NAVER_REDIRECT_URI: 'https://api.alphamate.kr/api/auth/naver/callback',
    VITE_ADMOB_ANDROID_APP_ID: 'ca-app-pub-1234567890123456~1234567890',
    VITE_ADMOB_REWARDED_AD_UNIT_ID: 'ca-app-pub-1234567890123456/9876543210',
    VITE_ADMOB_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT_ID: 'ca-app-pub-1234567890123456/1234567890',
    VITE_ADMOB_RESUME_INTERSTITIAL_AD_UNIT_ID: 'ca-app-pub-1234567890123456/3333333333',
    VITE_ADMOB_CHART_DETAIL_INTERSTITIAL_AD_UNIT_ID: 'ca-app-pub-1234567890123456/4444444444',
    VITE_ADMOB_BANNER_AD_UNIT_ID: 'ca-app-pub-1234567890123456/2222222222',
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
    VITE_ADMOB_ANDROID_APP_ID: 'ca-app-pub-3940256099942544~3347511713',
    VITE_ADMOB_REWARDED_AD_UNIT_ID: 'ca-app-pub-3940256099942544/5224354917',
    VITE_ADMOB_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT_ID: 'ca-app-pub-3940256099942544/1033173712',
    VITE_ADMOB_RESUME_INTERSTITIAL_AD_UNIT_ID: 'ca-app-pub-3940256099942544/1033173712',
    VITE_ADMOB_CHART_DETAIL_INTERSTITIAL_AD_UNIT_ID: 'ca-app-pub-3940256099942544/1033173712',
    VITE_ADMOB_BANNER_AD_UNIT_ID: 'ca-app-pub-3940256099942544/6300978111',
    VITE_GOOGLE_PLAY_PACKAGE_NAME: '',
  });

  assert.equal(result.ok, false);
  assert.match(result.errors.join('\n'), /VITE_ENABLE_DEV_TOOLS/);
  assert.match(result.errors.join('\n'), /VITE_API_BASE/);
  assert.match(result.errors.join('\n'), /VITE_ADMOB_ANDROID_APP_ID/);
  assert.match(result.errors.join('\n'), /VITE_ADMOB_REWARDED_AD_UNIT_ID/);
  assert.match(result.errors.join('\n'), /VITE_ADMOB_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT_ID/);
  assert.match(result.errors.join('\n'), /VITE_ADMOB_BANNER_AD_UNIT_ID/);
  assert.match(result.errors.join('\n'), /VITE_GOOGLE_PLAY_PACKAGE_NAME/);
});

test('rejects placeholder release URLs and AdMob ad unit IDs', () => {
  const result = validateReleaseEnv(validReleaseEnv({
    VITE_API_BASE: 'https://your-api.example.com',
    VITE_KAKAO_REDIRECT_URI: 'https://your-api.example.com/api/auth/kakao/callback',
    VITE_NAVER_REDIRECT_URI: 'https://your-api.example.com/api/auth/naver/callback',
    VITE_ADMOB_ANDROID_APP_ID: 'ca-app-pub-0000000000000000~0000000000',
    VITE_ADMOB_REWARDED_AD_UNIT_ID: 'ca-app-pub-0000000000000000/0000000000',
    VITE_ADMOB_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT_ID: 'ca-app-pub-0000000000000000/1111111111',
    VITE_ADMOB_RESUME_INTERSTITIAL_AD_UNIT_ID: 'ca-app-pub-0000000000000000/1111111111',
    VITE_ADMOB_CHART_DETAIL_INTERSTITIAL_AD_UNIT_ID: 'ca-app-pub-0000000000000000/1111111111',
    VITE_ADMOB_BANNER_AD_UNIT_ID: 'ca-app-pub-0000000000000000/1111111111',
  }));

  assert.equal(result.ok, false);
  assert.match(result.errors.join('\n'), /VITE_API_BASE/);
  assert.match(result.errors.join('\n'), /VITE_KAKAO_REDIRECT_URI/);
  assert.match(result.errors.join('\n'), /VITE_NAVER_REDIRECT_URI/);
  assert.match(result.errors.join('\n'), /VITE_ADMOB_ANDROID_APP_ID/);
  assert.match(result.errors.join('\n'), /VITE_ADMOB_REWARDED_AD_UNIT_ID/);
  assert.match(result.errors.join('\n'), /VITE_ADMOB_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT_ID/);
  assert.match(result.errors.join('\n'), /VITE_ADMOB_BANNER_AD_UNIT_ID/);
  assert.match(result.errors.join('\n'), /placeholder/);
});

test('rejects all-zero AdMob publisher placeholder ad unit IDs even when unit digits differ', () => {
  const result = validateReleaseEnv(validReleaseEnv({
    VITE_ADMOB_REWARDED_AD_UNIT_ID: 'ca-app-pub-0000000000000000/2222222222',
    VITE_ADMOB_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT_ID: 'ca-app-pub-0000000000000000/3333333333',
    VITE_ADMOB_RESUME_INTERSTITIAL_AD_UNIT_ID: 'ca-app-pub-0000000000000000/4444444444',
    VITE_ADMOB_CHART_DETAIL_INTERSTITIAL_AD_UNIT_ID: 'ca-app-pub-0000000000000000/5555555555',
    VITE_ADMOB_BANNER_AD_UNIT_ID: 'ca-app-pub-0000000000000000/6666666666',
  }));

  assert.equal(result.ok, false);
  assert.match(result.errors.join('\n'), /VITE_ADMOB_REWARDED_AD_UNIT_ID/);
  assert.match(result.errors.join('\n'), /VITE_ADMOB_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT_ID/);
  assert.match(result.errors.join('\n'), /VITE_ADMOB_RESUME_INTERSTITIAL_AD_UNIT_ID/);
  assert.match(result.errors.join('\n'), /VITE_ADMOB_CHART_DETAIL_INTERSTITIAL_AD_UNIT_ID/);
  assert.match(result.errors.join('\n'), /VITE_ADMOB_BANNER_AD_UNIT_ID/);
  assert.match(result.errors.join('\n'), /placeholder/);
});

test('rejects malformed production AdMob ad unit IDs', () => {
  const result = validateReleaseEnv(validReleaseEnv({
    VITE_ADMOB_REWARDED_AD_UNIT_ID: 'not-an-ad-unit-id',
  }));

  assert.equal(result.ok, false);
  assert.match(result.errors.join('\n'), /VITE_ADMOB_REWARDED_AD_UNIT_ID must be a valid AdMob ad unit ID/);
});
test('rejects duplicate production AdMob ad unit IDs across placements', () => {
  const duplicateAdUnitId = 'ca-app-pub-1234567890123456/9876543210';
  const result = validateReleaseEnv(validReleaseEnv({
    VITE_ADMOB_REWARDED_AD_UNIT_ID: duplicateAdUnitId,
    VITE_ADMOB_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT_ID: duplicateAdUnitId,
    VITE_ADMOB_RESUME_INTERSTITIAL_AD_UNIT_ID: duplicateAdUnitId,
    VITE_ADMOB_CHART_DETAIL_INTERSTITIAL_AD_UNIT_ID: duplicateAdUnitId,
    VITE_ADMOB_BANNER_AD_UNIT_ID: duplicateAdUnitId,
  }));

  assert.equal(result.ok, false);
  assert.match(result.errors.join('\n'), /AdMob ad unit IDs must be unique across placements/);
});

test('requires public OAuth settings for release builds', () => {
  const result = validateReleaseEnv(validReleaseEnv({
    VITE_KAKAO_REST_API_KEY: '',
    VITE_KAKAO_REDIRECT_URI: '',
    VITE_NAVER_CLIENT_ID: '',
    VITE_NAVER_REDIRECT_URI: '',
  }));

  assert.equal(result.ok, false);
  assert.match(result.errors.join('\n'), /VITE_KAKAO_REST_API_KEY/);
  assert.match(result.errors.join('\n'), /VITE_KAKAO_REDIRECT_URI/);
  assert.match(result.errors.join('\n'), /VITE_NAVER_CLIENT_ID/);
  assert.match(result.errors.join('\n'), /VITE_NAVER_REDIRECT_URI/);
});

test('rejects invalid or local OAuth redirect URLs for release builds', () => {
  const result = validateReleaseEnv(validReleaseEnv({
    VITE_KAKAO_REDIRECT_URI: 'not-a-url',
    VITE_NAVER_REDIRECT_URI: 'http://localhost:5174/oauth/naver',
  }));

  assert.equal(result.ok, false);
  assert.match(result.errors.join('\n'), /VITE_KAKAO_REDIRECT_URI must be a valid URL/);
  assert.match(result.errors.join('\n'), /VITE_NAVER_REDIRECT_URI must use https:\/\/ for release builds/);
  assert.match(result.errors.join('\n'), /VITE_NAVER_REDIRECT_URI must not point to localhost or a local IP/);
});


test('rejects release package name that differs from fixed Android app identity', () => {
  const result = validateReleaseEnv(validReleaseEnv({
    VITE_GOOGLE_PLAY_PACKAGE_NAME: 'com.other.app',
  }));

  assert.equal(result.ok, false);
  assert.match(result.errors.join('\n'), /VITE_GOOGLE_PLAY_PACKAGE_NAME must be com\.mariocrat\.stockanalyze/);
});
test('requires separate production interstitial ad unit IDs for each placement', () => {
  const result = validateReleaseEnv(validReleaseEnv({
    VITE_ADMOB_RESUME_INTERSTITIAL_AD_UNIT_ID: '',
    VITE_ADMOB_CHART_DETAIL_INTERSTITIAL_AD_UNIT_ID: '',
  }));

  assert.equal(result.ok, false);
  assert.match(result.errors.join('\n'), /VITE_ADMOB_RESUME_INTERSTITIAL_AD_UNIT_ID/);
  assert.match(result.errors.join('\n'), /VITE_ADMOB_CHART_DETAIL_INTERSTITIAL_AD_UNIT_ID/);
});

test('accepts production release settings without exposing secret requirements', () => {
  const result = validateReleaseEnv(validReleaseEnv());

  assert.equal(result.ok, true);
  assert.deepEqual(result.errors, []);
});

test('owner frontend release report counts banner ad unit as part of AdMob readiness', () => {
  const result = validateReleaseEnv(validReleaseEnv({
    VITE_ADMOB_BANNER_AD_UNIT_ID: '',
  }));
  const report = formatOwnerFrontendReleaseReport(result, validReleaseEnv({
    VITE_ADMOB_BANNER_AD_UNIT_ID: '',
  }));

  assert.equal(result.ok, false);
  assert.match(result.errors.join('\n'), /VITE_ADMOB_BANNER_AD_UNIT_ID/);
  assert.doesNotMatch(report, /9\/9 \(100%\)/);
  assert.match(report, /VITE_ADMOB_BANNER_AD_UNIT_ID/);
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

test('owner frontend release report points local signing setup to the helper batch', () => {
  const result = validateReleaseEnv(validReleaseEnv({
    ALPHAMATE_ANDROID_KEYSTORE_FILE: '',
    ALPHAMATE_ANDROID_KEYSTORE_PASSWORD: '',
    ALPHAMATE_ANDROID_KEY_ALIAS: '',
    ALPHAMATE_ANDROID_KEY_PASSWORD: '',
  }));

  const report = formatOwnerFrontendReleaseReport(result, {
    VITE_APP_NAME: 'AlphaMate',
    VITE_GOOGLE_PLAY_PACKAGE_NAME: 'com.mariocrat.stockanalyze',
  });

  assert.match(report, /generate_android_upload_key\.bat를 실행해서 Android 서명 키와 비밀번호 빈 값을 채우기/);
  assert.doesNotMatch(report, /Android 서명 키 파일\n/);
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
    'VITE_ADMOB_ANDROID_APP_ID',
    'VITE_ADMOB_REWARDED_AD_UNIT_ID',
    'VITE_ADMOB_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT_ID',
    'VITE_ADMOB_RESUME_INTERSTITIAL_AD_UNIT_ID',
    'VITE_ADMOB_CHART_DETAIL_INTERSTITIAL_AD_UNIT_ID',
    'VITE_ADMOB_BANNER_AD_UNIT_ID',
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

test('frontend env templates do not document server-only secrets', () => {
  const templates = [
    fs.readFileSync(path.resolve(process.cwd(), '.env.example'), 'utf8'),
    fs.readFileSync(path.resolve(process.cwd(), '.env.release.example'), 'utf8'),
  ].join('\n');
  const serverOnlyNames = [
    'OPENAI_API_KEY',
    'ALPHAMATE_OPENAI_API_KEY',
    'KAKAO_CLIENT_SECRET',
    'NAVER_CLIENT_SECRET',
    'GOOGLE_PLAY_SERVICE_ACCOUNT_JSON',
    'GOOGLE_PLAY_SERVICE_ACCOUNT_FILE',
    'GOOGLE_PLAY_RTDN_SHARED_TOKEN',
    'GOOGLE_PLAY_RTDN_OIDC_AUDIENCE',
    'GOOGLE_PLAY_RTDN_OIDC_EMAIL',
    'ALPHAMATE_ADMIN_TOKEN',
    'ALPHAMATE_ACCOUNT_DB_PATH',
    'ALPHAMATE_JOURNAL_DB_PATH',
    'ALPHAMATE_ACCESS_DB_PATH',
    'ALPHAMATE_REVIEW_HISTORY_DB_PATH',
    'ALPHAMATE_EVENT_LOG_DB_PATH',
  ];

  for (const name of serverOnlyNames) {
    assert.doesNotMatch(templates, new RegExp(`(^|\\n)#?\\s*${name}=`), `${name} must stay out of frontend env templates`);
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
    'VITE_ADMOB_ANDROID_APP_ID',
    'VITE_ADMOB_REWARDED_AD_UNIT_ID',
    'VITE_ADMOB_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT_ID',
    'VITE_ADMOB_BANNER_AD_UNIT_ID',
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
    VITE_ADMOB_ANDROID_APP_ID: 'ca-app-pub-3940256099942544~3347511713',
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
  assert.match(report, /준비율: \d\/9 \(\d+%\)/);
  assert.match(report, /앱 이름: AlphaMate/);
  assert.match(report, /구글 플레이 패키지: com\.mariocrat\.stockanalyze/);
  assert.match(report, /다음에 할 일/);
  assert.match(report, /운영 모드로 바꾸기/);
  assert.match(report, /API 서버 주소를 운영 HTTPS 주소로 바꾸기/);
  assert.match(report, /AdMob 운영 광고 단위로 바꾸기/);
  assert.match(report, /https:\/\/apps\.admob\.com\//);
  assert.equal(report.match(/API 서버 주소를 운영 HTTPS 주소로 바꾸기/g).length, 1);
  assert.match(report, /내가 나중에 받아야 하는 정보\/파일/);
  assert.match(report, /운영 API 서버 HTTPS 주소/);
  assert.match(report, /VITE_ALPHAMATE_ENV/);
  assert.doesNotMatch(report, /never-print-this/);
});

test('owner frontend release report explains placeholder OAuth redirect URLs', () => {
  const result = validateReleaseEnv(validReleaseEnv({
    VITE_KAKAO_REDIRECT_URI: 'https://your-api.example.com/api/auth/kakao/callback',
    VITE_NAVER_REDIRECT_URI: 'https://your-api.example.com/api/auth/naver/callback',
  }));

  const report = formatOwnerFrontendReleaseReport(result, {
    VITE_APP_NAME: 'AlphaMate',
    VITE_GOOGLE_PLAY_PACKAGE_NAME: 'com.mariocrat.stockanalyze',
  });

  assert.match(report, /카카오 Redirect URI를 실제 운영 주소로 바꾸기/);
  assert.match(report, /네이버 Redirect URI를 실제 운영 주소로 바꾸기/);
});

test('owner frontend release report lists all next actions', () => {
  const result = {
    ok: false,
    errors: Array.from({ length: 12 }, (_, index) => `SETTING_${index} must be set for release builds.`),
  };
  const report = formatOwnerFrontendReleaseReport(result, {
    VITE_APP_NAME: 'AlphaMate',
    VITE_GOOGLE_PLAY_PACKAGE_NAME: 'com.mariocrat.stockanalyze',
  });

  assert.match(report, /SETTING_0/);
  assert.match(report, /SETTING_11/);
  assert.doesNotMatch(report, /그 외 누락 항목/);
});

test('owner frontend release report includes app name and version inputs', () => {
  const env = validReleaseEnv({
    VITE_APP_NAME: '',
    ALPHAMATE_ANDROID_APP_NAME: '',
    ALPHAMATE_ANDROID_VERSION_CODE: '',
    ALPHAMATE_ANDROID_VERSION_NAME: '',
  });
  const result = validateReleaseEnv(env);
  const report = formatOwnerFrontendReleaseReport(result, env);

  assert.equal(result.ok, false);
  assert.match(report, /최종 앱 이름/);
  assert.match(report, /Android 버전 코드/);
  assert.match(report, /Android 버전 이름/);
});

test('release env module can be imported from node eval without running the CLI guard', () => {
  const result = spawnSync(process.execPath, [
    '-e',
    "import('./scripts/validate-release-env.js').then(({ validateReleaseEnv }) => { const result = validateReleaseEnv({}); console.log(result.ok); })",
  ], {
    cwd: process.cwd(),
    encoding: 'utf8',
  });

  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /false/);
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

test('raw frontend release env CLI prints Korean pass and fail headings', () => {
  const script = path.resolve(process.cwd(), 'scripts/validate-release-env.js');
  const passed = spawnSync(process.execPath, [script], {
    cwd: process.cwd(),
    env: { ...process.env, ...validReleaseEnv() },
    encoding: 'utf8',
  });

  assert.equal(passed.status, 0, passed.stderr);
  assert.match(passed.stdout, /프론트 출시 환경 검사를 통과했습니다\./);

  const failed = spawnSync(process.execPath, [script], {
    cwd: process.cwd(),
    env: { ...process.env, ...validReleaseEnv({ VITE_API_BASE: 'http://127.0.0.1:8002' }) },
    encoding: 'utf8',
  });

  assert.equal(failed.status, 1);
  assert.match(failed.stderr, /프론트 출시 환경 검사 실패:/);
  assert.match(failed.stderr, /VITE_API_BASE/);
});

test('package script exposes owner release report command', () => {
  const pkg = JSON.parse(fs.readFileSync(path.resolve(process.cwd(), 'package.json'), 'utf8'));

  assert.equal(pkg.scripts['release:report'], 'node scripts/owner-release-report.js');
});

test('mobile release check uses owner-facing release report before building', () => {
  const pkg = JSON.parse(fs.readFileSync(path.resolve(process.cwd(), 'package.json'), 'utf8'));

  assert.equal(pkg.scripts['mobile:release:check'], 'npm run release:report && npm run mobile:build');
});
