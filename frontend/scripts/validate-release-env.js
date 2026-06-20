import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

const GOOGLE_ANDROID_TEST_REWARDED_AD_ID = 'ca-app-pub-3940256099942544/5224354917';
const GOOGLE_ANDROID_TEST_INTERSTITIAL_AD_ID = 'ca-app-pub-3940256099942544/1033173712';
const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', '0.0.0.0', '::1']);

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
}

function requireSetting(env, key, errors) {
  if (!envValue(env, key)) {
    errors.push(`${key} must be set for signed Android release builds.`);
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
  const rewardedAdUnitId = envValue(env, 'VITE_ADMOB_REWARDED_AD_UNIT_ID');
  const reviewHistoryInterstitialAdUnitId = envValue(env, 'VITE_ADMOB_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT_ID');
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
  if (!rewardedAdUnitId) {
    errors.push('VITE_ADMOB_REWARDED_AD_UNIT_ID must be set for release builds.');
  } else if (rewardedAdUnitId === GOOGLE_ANDROID_TEST_REWARDED_AD_ID) {
    errors.push('VITE_ADMOB_REWARDED_AD_UNIT_ID must not use Google test ad unit for release builds.');
  }
  if (!reviewHistoryInterstitialAdUnitId) {
    errors.push('VITE_ADMOB_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT_ID must be set for release builds.');
  } else if (reviewHistoryInterstitialAdUnitId === GOOGLE_ANDROID_TEST_INTERSTITIAL_AD_ID) {
    errors.push('VITE_ADMOB_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT_ID must not use Google test ad unit for release builds.');
  }
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

function loadLocalEnv() {
  const envPath = path.resolve(process.cwd(), '.env');
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
