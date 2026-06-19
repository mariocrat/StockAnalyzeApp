import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

test('Android app label is injected from release branding settings', () => {
  const gradle = fs.readFileSync('android/app/build.gradle', 'utf8');
  const stringsXml = fs.readFileSync('android/app/src/main/res/values/strings.xml', 'utf8');
  const indexHtml = fs.readFileSync('index.html', 'utf8');

  assert.match(gradle, /ALPHAMATE_ANDROID_APP_NAME/);
  assert.match(gradle, /VITE_APP_NAME/);
  assert.doesNotMatch(stringsXml, /<string name="app_name">AlphaMate<\/string>/);
  assert.doesNotMatch(stringsXml, /<string name="title_activity_main">AlphaMate<\/string>/);
  assert.doesNotMatch(indexHtml, /<title>AlphaMate<\/title>/);
  assert.match(indexHtml, /%APP_TITLE%/);
  assert.doesNotMatch(indexHtml, /%VITE_APP_NAME%/);
});
