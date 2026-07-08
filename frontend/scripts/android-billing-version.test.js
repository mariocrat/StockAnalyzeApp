import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

function billingClientVersionFromPluginGradle() {
  const gradlePath = path.resolve('node_modules/capacitor-plugin-cdv-purchase/android/build.gradle');
  const gradle = fs.readFileSync(gradlePath, 'utf8');
  const match = gradle.match(/com\.android\.billingclient:billing(?:-ktx)?:([0-9]+)\.([0-9]+)\.([0-9]+)/);
  if (!match) return null;
  return {
    major: Number(match[1]),
    minor: Number(match[2]),
    patch: Number(match[3]),
    version: `${match[1]}.${match[2]}.${match[3]}`,
  };
}

test('Google Play Billing client is version 8 or newer for Play Store updates', () => {
  const version = billingClientVersionFromPluginGradle();

  assert.ok(version, 'Billing client dependency should be declared by capacitor-plugin-cdv-purchase');
  assert.ok(version.major >= 8, `Billing client ${version.version} is older than required major version 8`);
});