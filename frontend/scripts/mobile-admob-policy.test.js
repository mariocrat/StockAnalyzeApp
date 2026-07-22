import test from 'node:test';
import assert from 'node:assert/strict';

import {
  DEFAULT_ANDROID_TEST_APP_OPEN_AD_ID,
  DEFAULT_ANDROID_TEST_INTERSTITIAL_AD_ID,
  DEFAULT_ANDROID_TEST_BANNER_AD_ID,
  DEFAULT_ANDROID_TEST_REWARDED_AD_ID,
  assertBannerAdCanRun,
  assertAppOpenAdCanRun,
  assertInterstitialAdCanRun,
  assertRewardedAdCanRun,
  createAdMobRuntimeStatus,
  shouldShowBannerAd,
  shouldShowChartDetailInterstitial,
  shouldShowResumeAppOpenAd,
} from '../src/mobile/admobPolicy.js';

test('blocks the Google rewarded test ad unit in production', () => {
  const status = createAdMobRuntimeStatus({
    appEnv: 'production',
    rewardedAdId: DEFAULT_ANDROID_TEST_REWARDED_AD_ID,
    interstitialAdId: DEFAULT_ANDROID_TEST_INTERSTITIAL_AD_ID,
    appOpenAdId: DEFAULT_ANDROID_TEST_APP_OPEN_AD_ID,
    bannerAdId: DEFAULT_ANDROID_TEST_BANNER_AD_ID,
    native: true,
    platform: 'android',
  });

  assert.equal(status.usingTestAdUnit, true);
  assert.equal(status.productionMisconfigured, true);
  assert.equal(status.available, false);
  assert.equal(status.usingTestInterstitialAdUnit, true);
  assert.equal(status.interstitialProductionMisconfigured, true);
  assert.equal(status.interstitialAvailable, false);
  assert.equal(status.usingTestAppOpenAdUnit, true);
  assert.equal(status.appOpenProductionMisconfigured, true);
  assert.equal(status.appOpenAvailable, false);
  assert.equal(status.usingTestBannerAdUnit, true);
  assert.equal(status.bannerProductionMisconfigured, true);
  assert.equal(status.bannerAvailable, false);
  assert.throws(
    () => assertAppOpenAdCanRun({
      appEnv: 'production',
      appOpenAdId: DEFAULT_ANDROID_TEST_APP_OPEN_AD_ID,
    }),
    /Production AdMob app open ad unit is not configured/,
  );
  assert.throws(
    () => assertRewardedAdCanRun({
      appEnv: 'production',
      rewardedAdId: DEFAULT_ANDROID_TEST_REWARDED_AD_ID,
      userId: 'user-1',
    }),
    /Production AdMob rewarded ad unit is not configured/,
  );
  assert.throws(
    () => assertInterstitialAdCanRun({
      appEnv: 'production',
      interstitialAdId: DEFAULT_ANDROID_TEST_INTERSTITIAL_AD_ID,
    }),
    /Production AdMob interstitial ad unit is not configured/,
  );
  assert.throws(
    () => assertBannerAdCanRun({
      appEnv: 'production',
      bannerAdId: DEFAULT_ANDROID_TEST_BANNER_AD_ID,
    }),
    /Production AdMob banner ad unit is not configured/,
  );
});

test('allows a real rewarded ad unit in production for a logged-in user', () => {
  const status = createAdMobRuntimeStatus({
    appEnv: 'production',
    rewardedAdId: 'ca-app-pub-1234567890123456/9876543210',
    interstitialAdId: 'ca-app-pub-1234567890123456/1234567890',
    appOpenAdId: 'ca-app-pub-1234567890123456/3333333333',
    bannerAdId: 'ca-app-pub-1234567890123456/2222222222',
    native: true,
    platform: 'android',
  });

  assert.equal(status.usingTestAdUnit, false);
  assert.equal(status.productionMisconfigured, false);
  assert.equal(status.available, true);
  assert.equal(status.usingTestInterstitialAdUnit, false);
  assert.equal(status.interstitialProductionMisconfigured, false);
  assert.equal(status.interstitialAvailable, true);
  assert.equal(status.usingTestAppOpenAdUnit, false);
  assert.equal(status.appOpenProductionMisconfigured, false);
  assert.equal(status.appOpenAvailable, true);
  assert.equal(status.usingTestBannerAdUnit, false);
  assert.equal(status.bannerProductionMisconfigured, false);
  assert.equal(status.bannerAvailable, true);
  assert.doesNotThrow(() => assertRewardedAdCanRun({
    appEnv: 'production',
    rewardedAdId: 'ca-app-pub-1234567890123456/9876543210',
    userId: 'user-1',
  }));
  assert.doesNotThrow(() => assertInterstitialAdCanRun({
    appEnv: 'production',
    interstitialAdId: 'ca-app-pub-1234567890123456/1234567890',
  }));
  assert.doesNotThrow(() => assertBannerAdCanRun({
    appEnv: 'production',
    bannerAdId: 'ca-app-pub-1234567890123456/2222222222',
  }));
  assert.doesNotThrow(() => assertAppOpenAdCanRun({
    appEnv: 'production',
    appOpenAdId: 'ca-app-pub-1234567890123456/3333333333',
  }));
});

test('keeps the rewarded test ad unit available in development', () => {
  const status = createAdMobRuntimeStatus({
    appEnv: 'development',
    rewardedAdId: DEFAULT_ANDROID_TEST_REWARDED_AD_ID,
    interstitialAdId: DEFAULT_ANDROID_TEST_INTERSTITIAL_AD_ID,
    appOpenAdId: DEFAULT_ANDROID_TEST_APP_OPEN_AD_ID,
    bannerAdId: DEFAULT_ANDROID_TEST_BANNER_AD_ID,
    native: true,
    platform: 'android',
  });

  assert.equal(status.usingTestAdUnit, true);
  assert.equal(status.productionMisconfigured, false);
  assert.equal(status.available, true);
  assert.equal(status.usingTestInterstitialAdUnit, true);
  assert.equal(status.interstitialProductionMisconfigured, false);
  assert.equal(status.interstitialAvailable, true);
  assert.equal(status.usingTestAppOpenAdUnit, true);
  assert.equal(status.appOpenProductionMisconfigured, false);
  assert.equal(status.appOpenAvailable, true);
  assert.equal(status.usingTestBannerAdUnit, true);
  assert.equal(status.bannerProductionMisconfigured, false);
  assert.equal(status.bannerAvailable, true);
});

test('suppresses every non-rewarded ad for Pro users', () => {
  assert.equal(shouldShowBannerAd({ plan: 'pro', native: true }), false);
  assert.equal(shouldShowResumeAppOpenAd({
    plan: 'pro',
    backgroundedAtMs: 1_000,
    nowMs: 100_000,
    lastShownAtMs: 0,
  }), false);
  assert.equal(shouldShowChartDetailInterstitial({
    plan: 'pro',
    detailOpenCount: 3,
  }), false);
});

test('shows bottom banner only for free users in the native app', () => {
  assert.equal(shouldShowBannerAd({ plan: 'free', native: true }), true);
  assert.equal(shouldShowBannerAd({ plan: 'free', native: false }), false);
});

test('shows app open ad on resume only after a meaningful break and cooldown', () => {
  assert.equal(shouldShowResumeAppOpenAd({
    plan: 'free',
    backgroundedAtMs: 1_000,
    nowMs: 91_000,
    lastShownAtMs: 0,
  }), true);
  assert.equal(shouldShowResumeAppOpenAd({
    plan: 'free',
    backgroundedAtMs: 1_000,
    nowMs: 89_999,
    lastShownAtMs: 0,
  }), false);
  assert.equal(shouldShowResumeAppOpenAd({
    plan: 'free',
    backgroundedAtMs: 1_000,
    nowMs: 121_000,
    lastShownAtMs: 30_000,
  }), false);
});

test('shows chart detail interstitial every third entry for free users', () => {
  assert.equal(shouldShowChartDetailInterstitial({ plan: 'free', detailOpenCount: 1 }), false);
  assert.equal(shouldShowChartDetailInterstitial({ plan: 'free', detailOpenCount: 2 }), false);
  assert.equal(shouldShowChartDetailInterstitial({ plan: 'free', detailOpenCount: 3 }), true);
  assert.equal(shouldShowChartDetailInterstitial({ plan: 'free', detailOpenCount: 6 }), true);
});

test('checks every interstitial placement before reporting production readiness', () => {
  const status = createAdMobRuntimeStatus({
    appEnv: 'production',
    rewardedAdId: 'ca-app-pub-1234567890123456/9876543210',
    interstitialAdIds: [
      'ca-app-pub-1234567890123456/1234567890',
      DEFAULT_ANDROID_TEST_INTERSTITIAL_AD_ID,
      'ca-app-pub-1234567890123456/4444444444',
    ],
    bannerAdId: 'ca-app-pub-1234567890123456/2222222222',
    native: true,
    platform: 'android',
  });

  assert.equal(status.usingTestInterstitialAdUnit, true);
  assert.equal(status.interstitialProductionMisconfigured, true);
  assert.equal(status.interstitialAvailable, false);
});
