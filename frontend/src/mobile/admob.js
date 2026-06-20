import { AdMob } from '@capacitor-community/admob';
import { Capacitor } from '@capacitor/core';
import {
  DEFAULT_ANDROID_TEST_INTERSTITIAL_AD_ID,
  DEFAULT_ANDROID_TEST_REWARDED_AD_ID,
  assertInterstitialAdCanRun,
  assertRewardedAdCanRun,
  createAdMobRuntimeStatus,
} from './admobPolicy';

const APP_ENV = import.meta.env.VITE_ALPHAMATE_ENV || (import.meta.env.PROD ? 'production' : 'development');
const REWARDED_AD_ID = import.meta.env.VITE_ADMOB_REWARDED_AD_UNIT_ID || DEFAULT_ANDROID_TEST_REWARDED_AD_ID;
const INTERSTITIAL_AD_ID = import.meta.env.VITE_ADMOB_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT_ID || DEFAULT_ANDROID_TEST_INTERSTITIAL_AD_ID;
const USING_TEST_AD_UNIT = REWARDED_AD_ID === DEFAULT_ANDROID_TEST_REWARDED_AD_ID;
const USING_TEST_INTERSTITIAL_AD_UNIT = INTERSTITIAL_AD_ID === DEFAULT_ANDROID_TEST_INTERSTITIAL_AD_ID;

let initializePromise = null;

export function getAdMobRuntimeStatus() {
  return createAdMobRuntimeStatus({
    appEnv: APP_ENV,
    rewardedAdId: REWARDED_AD_ID,
    interstitialAdId: INTERSTITIAL_AD_ID,
    native: Capacitor.isNativePlatform(),
    platform: Capacitor.getPlatform(),
  });
}

export async function initializeAdMob() {
  if (!Capacitor.isNativePlatform()) {
    return getAdMobRuntimeStatus();
  }
  if (!initializePromise) {
    initializePromise = AdMob.initialize({
      initializeForTesting: APP_ENV !== 'production' || USING_TEST_AD_UNIT,
    });
  }
  await initializePromise;
  return getAdMobRuntimeStatus();
}

export async function showRewardedReviewAd({ userId }) {
  if (!Capacitor.isNativePlatform()) {
    throw new Error('AdMob rewarded ads are available only in the mobile app.');
  }
  assertRewardedAdCanRun({ appEnv: APP_ENV, rewardedAdId: REWARDED_AD_ID, userId });

  await initializeAdMob();

  await AdMob.prepareRewardVideoAd({
    adId: REWARDED_AD_ID,
    isTesting: APP_ENV !== 'production' || USING_TEST_AD_UNIT,
    npa: true,
    immersiveMode: true,
    ssv: {
      userId: String(userId),
      customData: 'basic_review',
    },
  });

  return AdMob.showRewardVideoAd();
}

export async function showReviewHistoryInterstitial() {
  if (!Capacitor.isNativePlatform()) {
    return { skipped: true, reason: 'web' };
  }
  assertInterstitialAdCanRun({ appEnv: APP_ENV, interstitialAdId: INTERSTITIAL_AD_ID });

  await initializeAdMob();

  await AdMob.prepareInterstitial({
    adId: INTERSTITIAL_AD_ID,
    isTesting: APP_ENV !== 'production' || USING_TEST_INTERSTITIAL_AD_UNIT,
    npa: true,
  });
  await AdMob.showInterstitial();
  return { shown: true };
}
