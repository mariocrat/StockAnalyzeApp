export const DEFAULT_ANDROID_TEST_REWARDED_AD_ID = 'ca-app-pub-3940256099942544/5224354917';

export function isProductionAdMobMisconfigured({ appEnv, rewardedAdId }) {
  return appEnv === 'production' && rewardedAdId === DEFAULT_ANDROID_TEST_REWARDED_AD_ID;
}

export function createAdMobRuntimeStatus({ appEnv, rewardedAdId, native, platform }) {
  const usingTestAdUnit = rewardedAdId === DEFAULT_ANDROID_TEST_REWARDED_AD_ID;
  const productionMisconfigured = isProductionAdMobMisconfigured({ appEnv, rewardedAdId });

  return {
    native,
    platform,
    available: Boolean(native && !productionMisconfigured),
    usingTestAdUnit,
    productionMisconfigured,
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
