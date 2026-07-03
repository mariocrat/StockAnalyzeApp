import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

const GOOGLE_ANDROID_TEST_REWARDED_AD_ID = 'ca-app-pub-3940256099942544/5224354917';
const GOOGLE_ANDROID_TEST_INTERSTITIAL_AD_ID = 'ca-app-pub-3940256099942544/1033173712';
const GOOGLE_ANDROID_TEST_BANNER_AD_ID = 'ca-app-pub-3940256099942544/6300978111';
const GOOGLE_ANDROID_TEST_APP_ID = 'ca-app-pub-3940256099942544~3347511713';
const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', '0.0.0.0', '::1']);
const PLACEHOLDER_HOST_PARTS = ['example.com', 'your-api', 'your-app', 'your-domain', 'your-site'];
const PLACEHOLDER_AD_UNIT_PATTERN = /^ca-app-pub-0+\/[01]+$/;
const PLACEHOLDER_AD_APP_PATTERN = /^ca-app-pub-0+~[01]+$/;

export function parseEnvFile(text) {
  return String(text || '')
    .split(/\r?\n/)
    .reduce((env, line) => {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#')) return env;
      const eq = trimmed.indexOf('=');
      if (eq <= 0) return env;
      const key = trimmed.slice(0, eq).trim();
      let value = trimmed.slice(eq + 1).trim();
      if (
        (value.startsWith('"') && value.endsWith('"'))
        || (value.startsWith("'") && value.endsWith("'"))
      ) {
        value = value.slice(1, -1);
      }
      env[key] = value;
      return env;
    }, {});
}

function envValue(env, key) {
  return String(env[key] ?? '').trim();
}

function validateApiBase(value, errors) {
  if (!value) {
    errors.push('VITE_API_BASE must be set to your HTTPS backend URL.');
    return;
  }

  let url;
  try {
    url = new URL(value);
  } catch {
    errors.push('VITE_API_BASE must be a valid URL.');
    return;
  }

  if (url.protocol !== 'https:') {
    errors.push('VITE_API_BASE must use https:// for release builds.');
  }
  if (LOCAL_HOSTS.has(url.hostname) || url.hostname.startsWith('127.')) {
    errors.push('VITE_API_BASE must not point to localhost or a local IP for release builds.');
  }
  if (isPlaceholderUrl(value)) {
    errors.push('VITE_API_BASE must not use a placeholder URL for release builds.');
  }
}

function isPlaceholderUrl(value) {
  if (!value) return false;
  try {
    const url = new URL(value);
    return PLACEHOLDER_HOST_PARTS.some((part) => url.hostname.includes(part));
  } catch {
    return false;
  }
}

function validatePublicHttpsUrl(env, key, errors) {
  const value = envValue(env, key);
  if (!value) return;

  let url;
  try {
    url = new URL(value);
  } catch {
    errors.push(`${key} must be a valid URL.`);
    return;
  }

  if (url.protocol !== 'https:') {
    errors.push(`${key} must use https:// for release builds.`);
  }
  if (LOCAL_HOSTS.has(url.hostname) || url.hostname.startsWith('127.')) {
    errors.push(`${key} must not point to localhost or a local IP for release builds.`);
  }
  if (isPlaceholderUrl(value)) {
    errors.push(`${key} must not use a placeholder URL for release builds.`);
  }
}

function validateAdUnitId(value, key, googleTestId, errors) {
  if (!value) {
    errors.push(`${key} must be set for release builds.`);
  } else if (value === googleTestId) {
    errors.push(`${key} must not use Google test ad unit for release builds.`);
  } else if (PLACEHOLDER_AD_UNIT_PATTERN.test(value)) {
    errors.push(`${key} must not use a placeholder ad unit ID for release builds.`);
  }
}

function validateAdMobAppId(value, errors) {
  if (!value) {
    errors.push('VITE_ADMOB_ANDROID_APP_ID must be set for release builds.');
  } else if (value === GOOGLE_ANDROID_TEST_APP_ID) {
    errors.push('VITE_ADMOB_ANDROID_APP_ID must not use Google test app ID for release builds.');
  } else if (PLACEHOLDER_AD_APP_PATTERN.test(value)) {
    errors.push('VITE_ADMOB_ANDROID_APP_ID must not use a placeholder app ID for release builds.');
  } else if (!/^ca-app-pub-\d{16}~\d{10}$/.test(value)) {
    errors.push('VITE_ADMOB_ANDROID_APP_ID must be a valid AdMob Android app ID.');
  }
}

function validateDistinctAdUnitIds(entries, errors) {
  const seen = new Map();
  entries
    .filter(([, value]) => Boolean(value))
    .forEach(([key, value]) => {
      const previousKey = seen.get(value);
      if (previousKey) {
        errors.push(`AdMob ad unit IDs must be unique across placements: ${previousKey} and ${key}.`);
        return;
      }
      seen.set(value, key);
    });
}

function requireSetting(env, key, errors) {
  if (!envValue(env, key)) {
    errors.push(`${key} must be set for signed Android release builds.`);
  }
}

function requireReleaseSetting(env, key, errors) {
  if (!envValue(env, key)) {
    errors.push(`${key} must be set for release builds.`);
  }
}

function validateKeystoreFile(env, errors) {
  const keystoreFile = envValue(env, 'ALPHAMATE_ANDROID_KEYSTORE_FILE');
  if (!keystoreFile) return;
  if (!fs.existsSync(path.resolve(keystoreFile))) {
    errors.push('ALPHAMATE_ANDROID_KEYSTORE_FILE does not exist.');
  }
}

function validateAndroidVersion(env, errors) {
  const versionCode = envValue(env, 'ALPHAMATE_ANDROID_VERSION_CODE');
  const versionName = envValue(env, 'ALPHAMATE_ANDROID_VERSION_NAME');
  if (!/^[1-9]\d*$/.test(versionCode)) {
    errors.push('ALPHAMATE_ANDROID_VERSION_CODE must be a positive integer.');
  }
  if (!/^\d+\.\d+\.\d+([+-][0-9A-Za-z.-]+)?$/.test(versionName)) {
    errors.push('ALPHAMATE_ANDROID_VERSION_NAME must use a version like 1.0.0.');
  }
}

export function validateReleaseEnv(env) {
  const errors = [];
  const appEnv = envValue(env, 'VITE_ALPHAMATE_ENV');
  const appName = envValue(env, 'ALPHAMATE_ANDROID_APP_NAME') || envValue(env, 'VITE_APP_NAME');
  const devTools = envValue(env, 'VITE_ENABLE_DEV_TOOLS');
  const apiBase = envValue(env, 'VITE_API_BASE');
  const androidAdMobAppId = envValue(env, 'VITE_ADMOB_ANDROID_APP_ID');
  const rewardedAdUnitId = envValue(env, 'VITE_ADMOB_REWARDED_AD_UNIT_ID');
  const reviewHistoryInterstitialAdUnitId = envValue(env, 'VITE_ADMOB_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT_ID');
  const bannerAdUnitId = envValue(env, 'VITE_ADMOB_BANNER_AD_UNIT_ID');
  const packageName = envValue(env, 'VITE_GOOGLE_PLAY_PACKAGE_NAME');

  if (appEnv !== 'production') {
    errors.push('VITE_ALPHAMATE_ENV must be production for release builds.');
  }
  if (!appName) {
    errors.push('VITE_APP_NAME or ALPHAMATE_ANDROID_APP_NAME must be set for release builds.');
  }
  if (devTools !== 'false') {
    errors.push('VITE_ENABLE_DEV_TOOLS must be false for release builds.');
  }
  validateApiBase(apiBase, errors);
  requireReleaseSetting(env, 'VITE_KAKAO_REST_API_KEY', errors);
  requireReleaseSetting(env, 'VITE_KAKAO_REDIRECT_URI', errors);
  requireReleaseSetting(env, 'VITE_NAVER_CLIENT_ID', errors);
  requireReleaseSetting(env, 'VITE_NAVER_REDIRECT_URI', errors);
  validatePublicHttpsUrl(env, 'VITE_KAKAO_REDIRECT_URI', errors);
  validatePublicHttpsUrl(env, 'VITE_NAVER_REDIRECT_URI', errors);
  validateAdMobAppId(androidAdMobAppId, errors);
  validateAdUnitId(rewardedAdUnitId, 'VITE_ADMOB_REWARDED_AD_UNIT_ID', GOOGLE_ANDROID_TEST_REWARDED_AD_ID, errors);
  validateAdUnitId(
    reviewHistoryInterstitialAdUnitId,
    'VITE_ADMOB_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT_ID',
    GOOGLE_ANDROID_TEST_INTERSTITIAL_AD_ID,
    errors,
  );
  validateAdUnitId(bannerAdUnitId, 'VITE_ADMOB_BANNER_AD_UNIT_ID', GOOGLE_ANDROID_TEST_BANNER_AD_ID, errors);
  validateDistinctAdUnitIds([
    ['VITE_ADMOB_REWARDED_AD_UNIT_ID', rewardedAdUnitId],
    ['VITE_ADMOB_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT_ID', reviewHistoryInterstitialAdUnitId],
    ['VITE_ADMOB_BANNER_AD_UNIT_ID', bannerAdUnitId],
  ], errors);
  if (!/^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){2,}$/.test(packageName)) {
    errors.push('VITE_GOOGLE_PLAY_PACKAGE_NAME must be a valid Android package name.');
  }
  requireSetting(env, 'ALPHAMATE_ANDROID_KEYSTORE_FILE', errors);
  requireSetting(env, 'ALPHAMATE_ANDROID_KEYSTORE_PASSWORD', errors);
  requireSetting(env, 'ALPHAMATE_ANDROID_KEY_ALIAS', errors);
  requireSetting(env, 'ALPHAMATE_ANDROID_KEY_PASSWORD', errors);
  validateKeystoreFile(env, errors);
  validateAndroidVersion(env, errors);

  return { ok: errors.length === 0, errors };
}

function publicEnvValue(env, key, fallback = '미설정') {
  const value = envValue(env, key);
  return value || fallback;
}

function statusLabel(ok) {
  return ok ? '준비됨' : '준비 필요';
}

function hasError(result, keyword) {
  return result.errors.some((error) => error.includes(keyword));
}

function lineForSetting(label, ready, detail = '') {
  return `- [${statusLabel(ready)}] ${label}${detail ? `: ${detail}` : ''}`;
}

function ownerFrontendNextAction(error) {
  if (error.includes('ALPHAMATE_ANDROID_KEYSTORE_FILE')
    || error.includes('ALPHAMATE_ANDROID_KEYSTORE_PASSWORD')
    || error.includes('ALPHAMATE_ANDROID_KEY_ALIAS')
    || error.includes('ALPHAMATE_ANDROID_KEY_PASSWORD')) {
    return 'generate_android_upload_key.bat를 실행해서 Android 서명 키와 비밀번호 빈 값을 채우기';
  }
  if (error.includes('VITE_ADMOB_ANDROID_APP_ID')) {
    return 'AdMob Android App ID를 운영 앱 ID로 바꾸기 (VITE_ADMOB_ANDROID_APP_ID) - https://apps.admob.com/';
  }
  if (error.includes('VITE_ADMOB_BANNER_AD_UNIT_ID')) {
    return 'AdMob 배너 광고 단위를 운영 광고 단위로 바꾸기 (VITE_ADMOB_BANNER_AD_UNIT_ID) - https://apps.admob.com/';
  }
  const hints = [
    ['VITE_ALPHAMATE_ENV', '운영 모드로 바꾸기'],
    ['VITE_APP_NAME', '앱 이름을 최종 이름으로 설정하기'],
    ['VITE_ENABLE_DEV_TOOLS', '개발 도구를 꺼서 운영 빌드에 노출되지 않게 하기'],
    ['VITE_API_BASE', 'API 서버 주소를 운영 HTTPS 주소로 바꾸기'],
    ['VITE_ADMOB_REWARDED_AD_UNIT_ID', 'AdMob 운영 광고 단위로 바꾸기', 'https://apps.admob.com/'],
    ['VITE_ADMOB_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT_ID', '복기 보관함 전면 광고 단위를 운영 광고 단위로 바꾸기', 'https://apps.admob.com/'],
    ['VITE_KAKAO_REST_API_KEY', '카카오 REST API Key를 앱 공개 설정에 넣기', 'https://developers.kakao.com/console/app'],
    ['VITE_KAKAO_REDIRECT_URI', '카카오 Redirect URI를 실제 운영 주소로 바꾸기', 'https://developers.kakao.com/console/app'],
    ['VITE_NAVER_CLIENT_ID', '네이버 Client ID를 앱 공개 설정에 넣기', 'https://developers.naver.com/apps/'],
    ['VITE_NAVER_REDIRECT_URI', '네이버 Redirect URI를 실제 운영 주소로 바꾸기', 'https://developers.naver.com/apps/'],
    ['VITE_GOOGLE_PLAY_PACKAGE_NAME', 'Google Play 패키지명을 Android 앱 설정과 맞추기', 'https://play.google.com/console'],
    ['ALPHAMATE_ANDROID_VERSION_CODE', 'Android 버전 코드를 이전 업로드보다 크게 올리기'],
    ['ALPHAMATE_ANDROID_VERSION_NAME', 'Android 버전 이름을 설정하기'],
  ];
  const match = hints.find(([setting]) => error.includes(setting));
  if (!match) return error;
  return `${match[1]} (${match[0]})${match[2] ? ` - ${match[2]}` : ''}`;
}

function ownerFrontendNextActions(errors) {
  return [...new Set(errors.map(ownerFrontendNextAction))];
}

function ownerFrontendRequiredInputs(errors) {
  const inputs = [];
  if (errors.some((error) => error.includes('VITE_API_BASE'))) {
    inputs.push('운영 API 서버 HTTPS 주소');
  }
  if (errors.some((error) => error.includes('VITE_ADMOB_ANDROID_APP_ID'))) {
    inputs.push('AdMob Android App ID');
  }
  if (errors.some((error) => error.includes('VITE_ADMOB_REWARDED_AD_UNIT_ID'))) {
    inputs.push('AdMob 보상형 광고 단위 ID');
  }
  if (errors.some((error) => error.includes('VITE_ADMOB_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT_ID'))) {
    inputs.push('AdMob 복기 보관함 전면 광고 단위 ID');
  }
  if (errors.some((error) => error.includes('VITE_ADMOB_BANNER_AD_UNIT_ID'))) {
    inputs.push('AdMob 배너 광고 단위 ID');
  }
  if (errors.some((error) => error.includes('VITE_KAKAO_REST_API_KEY'))) {
    inputs.push('카카오 REST API Key 값');
  }
  if (errors.some((error) => error.includes('VITE_KAKAO_REDIRECT_URI'))) {
    inputs.push('카카오 Redirect URI 운영 주소');
  }
  if (errors.some((error) => error.includes('VITE_NAVER_CLIENT_ID'))) {
    inputs.push('네이버 Client ID 값');
  }
  if (errors.some((error) => error.includes('VITE_NAVER_REDIRECT_URI'))) {
    inputs.push('네이버 Redirect URI 운영 주소');
  }
  if (errors.some((error) => error.includes('VITE_GOOGLE_PLAY_PACKAGE_NAME'))) {
    inputs.push('Google Play 패키지명');
  }
  return inputs;
}

export function formatOwnerFrontendReleaseReport(result, env = releaseEnvFromProcess()) {
  const appName = publicEnvValue(env, 'ALPHAMATE_ANDROID_APP_NAME', envValue(env, 'VITE_APP_NAME') || '미설정');
  const packageName = publicEnvValue(env, 'VITE_GOOGLE_PLAY_PACKAGE_NAME');
  const appEnvReady = !hasError(result, 'VITE_ALPHAMATE_ENV');
  const appNameReady = !hasError(result, 'VITE_APP_NAME') && appName !== '미설정';
  const devToolsReady = !hasError(result, 'VITE_ENABLE_DEV_TOOLS');
  const apiReady = !hasError(result, 'VITE_API_BASE');
  const oauthReady = !hasError(result, 'VITE_KAKAO_REST_API_KEY')
    && !hasError(result, 'VITE_KAKAO_REDIRECT_URI')
    && !hasError(result, 'VITE_NAVER_CLIENT_ID')
    && !hasError(result, 'VITE_NAVER_REDIRECT_URI');
  const admobReady = !hasError(result, 'VITE_ADMOB_ANDROID_APP_ID')
    && !hasError(result, 'VITE_ADMOB_REWARDED_AD_UNIT_ID')
    && !hasError(result, 'VITE_ADMOB_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT_ID')
    && !hasError(result, 'VITE_ADMOB_BANNER_AD_UNIT_ID');
  const packageReady = !hasError(result, 'VITE_GOOGLE_PLAY_PACKAGE_NAME');
  const signingReady = !hasError(result, 'ALPHAMATE_ANDROID_KEYSTORE_FILE')
    && !hasError(result, 'ALPHAMATE_ANDROID_KEYSTORE_PASSWORD')
    && !hasError(result, 'ALPHAMATE_ANDROID_KEY_ALIAS')
    && !hasError(result, 'ALPHAMATE_ANDROID_KEY_PASSWORD');
  const versionReady = !hasError(result, 'ALPHAMATE_ANDROID_VERSION_CODE')
    && !hasError(result, 'ALPHAMATE_ANDROID_VERSION_NAME');
  const readinessItems = [
    appEnvReady,
    appNameReady,
    devToolsReady,
    apiReady,
    oauthReady,
    admobReady,
    packageReady,
    signingReady,
    versionReady,
  ];
  const readyCount = readinessItems.filter(Boolean).length;
  const readyPercent = Math.round((readyCount / readinessItems.length) * 100);

  const lines = [
    'AlphaMate 프론트/앱 출시 준비 보고서',
    '',
    `전체 상태: ${statusLabel(result.ok)}`,
    `준비율: ${readyCount}/${readinessItems.length} (${readyPercent}%)`,
    '',
    `앱 이름: ${appName}`,
    `구글 플레이 패키지: ${packageName}`,
    '',
    '항목별 상태:',
    lineForSetting('운영 모드', appEnvReady),
    lineForSetting('앱 이름', appNameReady, appName),
    lineForSetting('개발 도구 비활성화', devToolsReady),
    lineForSetting('API 서버 주소', apiReady),
    lineForSetting('카카오/네이버 로그인 공개 설정', oauthReady),
    lineForSetting('AdMob 광고 단위', admobReady),
    lineForSetting('Google Play 패키지명', packageReady, packageName),
    lineForSetting('Android 서명 키', signingReady),
    lineForSetting('Android 버전', versionReady),
    '',
    '다음에 할 일:',
  ];

  if (result.errors.length === 0) {
    lines.push('1. 실제 기기에서 로그인, 결제, 광고, AI 복기를 수동으로 확인하세요.');
  } else {
    const nextActions = ownerFrontendNextActions(result.errors);
    nextActions.forEach((action, index) => {
      lines.push(`${index + 1}. ${action}`);
    });
  }

  const requiredInputs = ownerFrontendRequiredInputs(result.errors);
  if (requiredInputs.length > 0) {
    lines.push('', '내가 나중에 받아야 하는 정보/파일:');
    requiredInputs.forEach((input, index) => {
      lines.push(`${index + 1}. ${input}`);
    });
  }

  lines.push(
    '',
    '주의: 이 보고서는 필요한 설정 이름과 공개 식별자만 보여주고 비밀번호, 키스토어 암호, API Key 값은 출력하지 않습니다.',
  );
  return lines.join('\n');
}

function loadLocalEnv() {
  const configuredEnvPath = envValue(process.env, 'ALPHAMATE_FRONTEND_ENV_FILE');
  const envPath = configuredEnvPath
    ? path.resolve(configuredEnvPath)
    : path.resolve(process.cwd(), '.env');
  if (!fs.existsSync(envPath)) return {};
  return parseEnvFile(fs.readFileSync(envPath, 'utf8'));
}

export function releaseEnvFromProcess() {
  return {
    ...loadLocalEnv(),
    ...process.env,
  };
}

if (fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  const result = validateReleaseEnv(releaseEnvFromProcess());
  if (!result.ok) {
    console.error('Release environment check failed:');
    for (const error of result.errors) {
      console.error(`- ${error}`);
    }
    process.exit(1);
  }
  console.log('Release environment check passed.');
}
