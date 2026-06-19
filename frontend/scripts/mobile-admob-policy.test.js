import test from 'node:test';
import assert from 'node:assert/strict';

import {
  DEFAULT_ANDROID_TEST_REWARDED_AD_ID,
  assertRewardedAdCanRun,
  createAdMobRuntimeStatus,
} from '../src/mobile/admobPolicy.js';

test('blocks the Google rewarded test ad unit in production', () => {
  const status = createAdMobRuntimeStatus({
    appEnv: 'production',
    rewardedAdId: DEFAULT_ANDROID_TEST_REWARDED_AD_ID,
    native: true,
    platform: 'android',
  });

  assert.equal(status.usingTestAdUnit, true);
  assert.equal(status.productionMisconfigured, true);
  assert.equal(status.available, false);
  assert.throws(
    () => assertRewardedAdCanRun({
      appEnv: 'production',
      rewardedAdId: DEFAULT_ANDROID_TEST_REWARDED_AD_ID,
      userId: 'user-1',
    }),
    /Production AdMob rewarded ad unit is not configured/,
  );
});

test('allows a real rewarded ad unit in production for a logged-in user', () => {
  const status = createAdMobRuntimeStatus({
    appEnv: 'production',
    rewardedAdId: 'ca-app-pub-1234567890123456/9876543210',
    native: true,
    platform: 'android',
  });

  assert.equal(status.usingTestAdUnit, false);
  assert.equal(status.productionMisconfigured, false);
  assert.equal(status.available, true);
  assert.doesNotThrow(() => assertRewardedAdCanRun({
    appEnv: 'production',
    rewardedAdId: 'ca-app-pub-1234567890123456/9876543210',
    userId: 'user-1',
  }));
});

test('keeps the rewarded test ad unit available in development', () => {
  const status = createAdMobRuntimeStatus({
    appEnv: 'development',
    rewardedAdId: DEFAULT_ANDROID_TEST_REWARDED_AD_ID,
    native: true,
    platform: 'android',
  });

  assert.equal(status.usingTestAdUnit, true);
  assert.equal(status.productionMisconfigured, false);
  assert.equal(status.available, true);
});
