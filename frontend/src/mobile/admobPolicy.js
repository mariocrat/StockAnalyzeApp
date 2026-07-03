export const DEFAULT_ANDROID_TEST_REWARDED_AD_ID = 'ca-app-pub-3940256099942544/5224354917';
export const DEFAULT_ANDROID_TEST_INTERSTITIAL_AD_ID = 'ca-app-pub-3940256099942544/1033173712';
export const DEFAULT_ANDROID_TEST_BANNER_AD_ID = 'ca-app-pub-3940256099942544/6300978111';
export const RESUME_INTERSTITIAL_MIN_BACKGROUND_MS = 90_000;
export const RESUME_INTERSTITIAL_COOLDOWN_MS = 600_000;
export const CHART_DETAIL_INTERSTITIAL_FREQUENCY = 3;

export function isProductionAdMobMisconfigured({ appEnv, rewardedAdId }) {
  return appEnv === 'production' && rewardedAdId === DEFAULT_ANDROID_TEST_REWARDED_AD_ID;
}

export function isProductionInterstitialMisconfigured({ appEnv, interstitialAdId }) {
  return appEnv === 'production' && interstitialAdId === DEFAULT_ANDROID_TEST_INTERSTITIAL_AD_ID;
}

export function isProductionBannerMisconfigured({ appEnv, bannerAdId }) {
  return appEnv === 'production' && bannerAdId === DEFAULT_ANDROID_TEST_BANNER_AD_ID;
}

export function createAdMobRuntimeStatus({
  appEnv,
  rewardedAdId,
  interstitialAdId = DEFAULT_ANDROID_TEST_INTERSTITIAL_AD_ID,
  bannerAdId = DEFAULT_ANDROID_TEST_BANNER_AD_ID,
  native,
  platform,
}) {
  const usingTestAdUnit = rewardedAdId === DEFAULT_ANDROID_TEST_REWARDED_AD_ID;
  const productionMisconfigured = isProductionAdMobMisconfigured({ appEnv, rewardedAdId });
  const usingTestInterstitialAdUnit = interstitialAdId === DEFAULT_ANDROID_TEST_INTERSTITIAL_AD_ID;
  const interstitialProductionMisconfigured = isProductionInterstitialMisconfigured({ appEnv, interstitialAdId });
  const usingTestBannerAdUnit = bannerAdId === DEFAULT_ANDROID_TEST_BANNER_AD_ID;
  const bannerProductionMisconfigured = isProductionBannerMisconfigured({ appEnv, bannerAdId });

  return {
    native,
    platform,
    available: Boolean(native && !productionMisconfigured),
    interstitialAvailable: Boolean(native && !interstitialProductionMisconfigured),
    bannerAvailable: Boolean(native && !bannerProductionMisconfigured),
    usingTestAdUnit,
    usingTestInterstitialAdUnit,
    usingTestBannerAdUnit,
    productionMisconfigured,
    interstitialProductionMisconfigured,
    bannerProductionMisconfigured,
  };
}

export function assertRewardedAdCanRun({ appEnv, rewardedAdId, userId }) {
  if (isProductionAdMobMisconfigured({ appEnv, rewardedAdId })) {
    throw new Error('Production AdMob rewarded ad unit is not configured.');
  }
  if (!userId) {
    throw new Error('A logged-in user is required before watching a rewarded ad.');
  }
}

export function assertInterstitialAdCanRun({ appEnv, interstitialAdId }) {
  if (isProductionInterstitialMisconfigured({ appEnv, interstitialAdId })) {
    throw new Error('Production AdMob interstitial ad unit is not configured.');
  }
}

export function assertBannerAdCanRun({ appEnv, bannerAdId }) {
  if (isProductionBannerMisconfigured({ appEnv, bannerAdId })) {
    throw new Error('Production AdMob banner ad unit is not configured.');
  }
}

export function isAdFreePlan(plan) {
  return plan === 'pro';
}

export function shouldShowBannerAd({ plan, native }) {
  if (isAdFreePlan(plan)) return false;
  return Boolean(native);
}

export function shouldShowResumeInterstitial({
  plan,
  backgroundedAtMs,
  nowMs,
  lastShownAtMs = 0,
  minBackgroundMs = RESUME_INTERSTITIAL_MIN_BACKGROUND_MS,
  cooldownMs = RESUME_INTERSTITIAL_COOLDOWN_MS,
}) {
  if (isAdFreePlan(plan)) return false;
  if (!backgroundedAtMs || !nowMs) return false;
  if (nowMs - backgroundedAtMs < minBackgroundMs) return false;
  if (lastShownAtMs && nowMs - lastShownAtMs < cooldownMs) return false;
  return true;
}

export function shouldShowChartDetailInterstitial({
  plan,
  detailOpenCount,
  frequency = CHART_DETAIL_INTERSTITIAL_FREQUENCY,
}) {
  if (isAdFreePlan(plan)) return false;
  if (!Number.isFinite(detailOpenCount) || detailOpenCount < 1) return false;
  return detailOpenCount % frequency === 0;
}
