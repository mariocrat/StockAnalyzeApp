import { test, ownedTempDir, checkFailureCleanup } from './release-test-isolation.mjs';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

import { validateMobileBundle } from './validate-mobile-bundle.js';

function fixture(content) {
  const dir = ownedTempDir('alphamate-mobile-bundle-');
  fs.writeFileSync(path.join(dir, 'index.js'), content);
  return dir;
}

test('accepts a bundle that targets the release API', () => {
  const result = validateMobileBundle({
    distDir: fixture('const API_BASE="https://api.alphamate.co.kr";'),
    expectedApiBase: 'https://api.alphamate.co.kr',
  });
  assert.deepEqual(result, { ok: true, errors: [] });
});

test('rejects a mobile bundle that still targets localhost', () => {
  const result = validateMobileBundle({
    distDir: fixture('const API_BASE="http://127.0.0.1:8002";'),
    expectedApiBase: 'https://api.alphamate.co.kr',
  });
  assert.equal(result.ok, false);
  assert.match(result.errors.join('\n'), /localhost API URL/);
  assert.match(result.errors.join('\n'), /release API URL/);
});

test('bundle fixtures restore temp env CWD and module state after success assertion and setup failure', () => {
  checkFailureCleanup();
});
