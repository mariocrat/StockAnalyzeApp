import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';

const appSource = fs.readFileSync(path.resolve('src/App.jsx'), 'utf8');

test('splash waits for initial theme loading with bounded timing', () => {
  assert.match(appSource, /const SPLASH_MIN_MS = 1150;/);
  assert.match(appSource, /const SPLASH_MAX_MS = 3500;/);
  assert.match(appSource, /const SPLASH_FADE_MS = 280;/);
  assert.match(appSource, /const splashStartedAtRef = useRef\(null\);/);
  assert.match(appSource, /const initialDataReady = !themesLoading \|\| Boolean\(themeError\);/);
  assert.match(appSource, /\[showSplash, themesLoading, themeError\]/);
  assert.doesNotMatch(appSource, /setTimeout\(\(\) => \{\s*setSplashExiting\(true\);\s*\}, 1150\)/s);
});
