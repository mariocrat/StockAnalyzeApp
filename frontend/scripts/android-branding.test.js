import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

test('Android app label is injected from release branding settings', () => {
  const gradle = fs.readFileSync('android/app/build.gradle', 'utf8');
  const stringsXml = fs.readFileSync('android/app/src/main/res/values/strings.xml', 'utf8');
  const indexHtml = fs.readFileSync('index.html', 'utf8');

  assert.match(gradle, /ALPHAMATE_ANDROID_APP_NAME/);
  assert.match(gradle, /VITE_APP_NAME/);
  assert.match(gradle, /VITE_GOOGLE_PLAY_PACKAGE_NAME/);
  assert.match(gradle, /VITE_ADMOB_ANDROID_APP_ID/);
  assert.match(gradle, /applicationId androidPackageName/);
  assert.match(gradle, /resValue "string", "package_name", androidPackageName/);
  assert.match(gradle, /resValue "string", "custom_url_scheme", androidPackageName/);
  assert.match(gradle, /manifestPlaceholders/);
  assert.doesNotMatch(stringsXml, /<string name="app_name">AlphaMate<\/string>/);
  assert.doesNotMatch(stringsXml, /<string name="title_activity_main">AlphaMate<\/string>/);
  assert.doesNotMatch(stringsXml, /<string name="package_name">com\.mariocrat\.stockanalyze<\/string>/);
  assert.doesNotMatch(stringsXml, /<string name="custom_url_scheme">com\.mariocrat\.stockanalyze<\/string>/);
  assert.doesNotMatch(stringsXml, /ca-app-pub-3940256099942544~3347511713/);
  assert.doesNotMatch(indexHtml, /<title>AlphaMate<\/title>/);
  assert.match(indexHtml, /%APP_TITLE%/);
  assert.doesNotMatch(indexHtml, /%VITE_APP_NAME%/);
});

test('Android Manifest declares OAuth app return deep link for the package scheme', () => {
  const manifest = fs.readFileSync('android/app/src/main/AndroidManifest.xml', 'utf8');

  assert.match(manifest, /android:scheme="@string\/custom_url_scheme"/);
  assert.match(manifest, /android:host="oauth"/);
  assert.match(manifest, /android:pathPrefix="\/kakao"/);
  assert.match(manifest, /android:pathPrefix="\/naver"/);
  assert.match(manifest, /android.intent.action.VIEW/);
  assert.match(manifest, /android.intent.category.BROWSABLE/);
});