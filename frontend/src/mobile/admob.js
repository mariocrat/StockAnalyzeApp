import { AdMob } from '@capacitor-community/admob';
import { Capacitor } from '@capacitor/core';

const DEFAULT_ANDROID_TEST_REWARDED_AD_ID = 'ca-app-pub-3940256099942544/5224354917';
const APP_ENV = import.meta.env.VITE_ALPHAMATE_ENV || (import.meta.env.PROD ? 'production' : 'development');
const REWARDED_AD_ID = import.meta.env.VITE_ADMOB_REWARDED_AD_UNIT_ID || DEFAULT_ANDROID_TEST_REWARDED_AD_ID;
const USING_TEST_AD_UNIT = REWARDED_AD_ID === DEFAULT_ANDROID_TEST_REWARDED_AD_ID;

let initializePromise = null;

export function getAdMobRuntimeStatus() {
  return {
    native: Capacitor.isNativePlatform(),
    platform: Capacitor.getPlatform(),
    usingTestAdUnit: USING_TEST_AD_UNIT,
  };
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
  if (!userId) {
    throw new Error('A logged-in user is required before watching a rewarded ad.');
  }

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
