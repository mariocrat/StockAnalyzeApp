export const DEFAULT_ANDROID_TEST_REWARDED_AD_ID = 'ca-app-pub-3940256099942544/5224354917';
export const DEFAULT_ANDROID_TEST_INTERSTITIAL_AD_ID = 'ca-app-pub-3940256099942544/1033173712';

export function isProductionAdMobMisconfigured({ appEnv, rewardedAdId }) {
  return appEnv === 'production' && rewardedAdId === DEFAULT_ANDROID_TEST_REWARDED_AD_ID;
}

export function isProductionInterstitialMisconfigured({ appEnv, interstitialAdId }) {
  return appEnv === 'production' && interstitialAdId === DEFAULT_ANDROID_TEST_INTERSTITIAL_AD_ID;
}

export function createAdMobRuntimeStatus({
  appEnv,
  rewardedAdId,
  interstitialAdId = DEFAULT_ANDROID_TEST_INTERSTITIAL_AD_ID,
  native,
  platform,
}) {
  const usingTestAdUnit = rewardedAdId === DEFAULT_ANDROID_TEST_REWARDED_AD_ID;
  const productionMisconfigured = isProductionAdMobMisconfigured({ appEnv, rewardedAdId });
  const usingTestInterstitialAdUnit = interstitialAdId === DEFAULT_ANDROID_TEST_INTERSTITIAL_AD_ID;
  const interstitialProductionMisconfigured = isProductionInterstitialMisconfigured({ appEnv, interstitialAdId });

  return {
    native,
    platform,
    available: Boolean(native && !productionMisconfigured),
    interstitialAvailable: Boolean(native && !interstitialProductionMisconfigured),
    usingTestAdUnit,
    usingTestInterstitialAdUnit,
    productionMisconfigured,
    interstitialProductionMisconfigured,
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
