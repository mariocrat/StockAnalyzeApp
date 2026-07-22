import { AdMob } from '@capacitor-community/admob';
import { Capacitor, registerPlugin } from '@capacitor/core';
import {
  DEFAULT_ANDROID_TEST_APP_OPEN_AD_ID,
  DEFAULT_ANDROID_TEST_BANNER_AD_ID,
  DEFAULT_ANDROID_TEST_INTERSTITIAL_AD_ID,
  DEFAULT_ANDROID_TEST_REWARDED_AD_ID,
  assertBannerAdCanRun,
  assertAppOpenAdCanRun,
  assertInterstitialAdCanRun,
  assertRewardedAdCanRun,
  createAdMobRuntimeStatus,
} from './admobPolicy';

const APP_ENV = import.meta.env.VITE_ALPHAMATE_ENV || (import.meta.env.PROD ? 'production' : 'development');
const REWARDED_AD_ID = import.meta.env.VITE_ADMOB_REWARDED_AD_UNIT_ID || DEFAULT_ANDROID_TEST_REWARDED_AD_ID;
const REVIEW_HISTORY_INTERSTITIAL_AD_ID = import.meta.env.VITE_ADMOB_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT_ID || DEFAULT_ANDROID_TEST_INTERSTITIAL_AD_ID;
const APP_OPEN_AD_ID = import.meta.env.VITE_ADMOB_APP_OPEN_AD_UNIT_ID || DEFAULT_ANDROID_TEST_APP_OPEN_AD_ID;
const CHART_DETAIL_INTERSTITIAL_AD_ID = import.meta.env.VITE_ADMOB_CHART_DETAIL_INTERSTITIAL_AD_UNIT_ID || DEFAULT_ANDROID_TEST_INTERSTITIAL_AD_ID;
const BANNER_AD_ID = import.meta.env.VITE_ADMOB_BANNER_AD_UNIT_ID || DEFAULT_ANDROID_TEST_BANNER_AD_ID;
const USING_TEST_AD_UNIT = REWARDED_AD_ID === DEFAULT_ANDROID_TEST_REWARDED_AD_ID;
const USING_TEST_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT = REVIEW_HISTORY_INTERSTITIAL_AD_ID === DEFAULT_ANDROID_TEST_INTERSTITIAL_AD_ID;
const USING_TEST_APP_OPEN_AD_UNIT = APP_OPEN_AD_ID === DEFAULT_ANDROID_TEST_APP_OPEN_AD_ID;
const USING_TEST_CHART_DETAIL_INTERSTITIAL_AD_UNIT = CHART_DETAIL_INTERSTITIAL_AD_ID === DEFAULT_ANDROID_TEST_INTERSTITIAL_AD_ID;
const USING_TEST_INTERSTITIAL_AD_UNIT = USING_TEST_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT
  || USING_TEST_CHART_DETAIL_INTERSTITIAL_AD_UNIT;
const USING_TEST_BANNER_AD_UNIT = BANNER_AD_ID === DEFAULT_ANDROID_TEST_BANNER_AD_ID;
const USING_ANY_TEST_AD_UNIT = USING_TEST_AD_UNIT || USING_TEST_INTERSTITIAL_AD_UNIT || USING_TEST_APP_OPEN_AD_UNIT || USING_TEST_BANNER_AD_UNIT;

const AlphaMateAppOpen = registerPlugin('AlphaMateAppOpen');

let initializePromise = null;

export function getAdMobRuntimeStatus() {
  return createAdMobRuntimeStatus({
    appEnv: APP_ENV,
    rewardedAdId: REWARDED_AD_ID,
    interstitialAdId: REVIEW_HISTORY_INTERSTITIAL_AD_ID,
    interstitialAdIds: [
      REVIEW_HISTORY_INTERSTITIAL_AD_ID,
      CHART_DETAIL_INTERSTITIAL_AD_ID,
    ],
    appOpenAdId: APP_OPEN_AD_ID,
    bannerAdId: BANNER_AD_ID,
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
      initializeForTesting: APP_ENV !== 'production' || USING_ANY_TEST_AD_UNIT,
    });
  }
  await initializePromise;
  // App Open inventory is opportunistic. A load failure must not block other ads.
  prepareResumeAppOpenAd().catch(() => {});
  return getAdMobRuntimeStatus();
}

async function prepareResumeAppOpenAd() {
  if (!Capacitor.isNativePlatform()) return { prepared: false, reason: 'web' };
  assertAppOpenAdCanRun({ appEnv: APP_ENV, appOpenAdId: APP_OPEN_AD_ID });
  return AlphaMateAppOpen.prepare({ adId: APP_OPEN_AD_ID });
}

export async function showRewardedReviewAd({ userId, purpose = 'basic_review' }) {
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
      customData: purpose,
    },
  });

  return AdMob.showRewardVideoAd();
}

async function showInterstitialAd(adId) {
  if (!Capacitor.isNativePlatform()) {
    return { skipped: true, reason: 'web' };
  }
  assertInterstitialAdCanRun({ appEnv: APP_ENV, interstitialAdId: adId });

  await initializeAdMob();

  await AdMob.prepareInterstitial({
    adId,
    isTesting: APP_ENV !== 'production' || adId === DEFAULT_ANDROID_TEST_INTERSTITIAL_AD_ID,
    npa: true,
  });
  await AdMob.showInterstitial();
  return { shown: true };
}

export async function showReviewHistoryInterstitial() {
  return showInterstitialAd(REVIEW_HISTORY_INTERSTITIAL_AD_ID);
}

export async function showResumeAppOpenAd() {
  if (!Capacitor.isNativePlatform()) {
    return { skipped: true, reason: 'web' };
  }
  assertAppOpenAdCanRun({ appEnv: APP_ENV, appOpenAdId: APP_OPEN_AD_ID });
  await initializeAdMob();
  const result = await AlphaMateAppOpen.show();
  prepareResumeAppOpenAd().catch(() => {});
  return result;
}

export async function showChartDetailInterstitial() {
  return showInterstitialAd(CHART_DETAIL_INTERSTITIAL_AD_ID);
}

export async function showAppBanner() {
  if (!Capacitor.isNativePlatform()) {
    return { skipped: true, reason: 'web' };
  }
  assertBannerAdCanRun({ appEnv: APP_ENV, bannerAdId: BANNER_AD_ID });

  await initializeAdMob();
  await AdMob.showBanner({
    adId: BANNER_AD_ID,
    adSize: 'ADAPTIVE_BANNER',
    position: 'BOTTOM_CENTER',
    isTesting: APP_ENV !== 'production' || USING_TEST_BANNER_AD_UNIT,
    npa: true,
    margin: 0,
  });
  return { shown: true };
}

export async function removeAppBanner() {
  if (!Capacitor.isNativePlatform()) {
    return { skipped: true, reason: 'web' };
  }
  await AdMob.removeBanner();
  return { removed: true };
}
