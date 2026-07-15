import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

import { parseEnvFile } from './validate-release-env.js';

const LOCAL_API_PATTERNS = [
  /https?:\/\/localhost:8002/i,
  /https?:\/\/127\.0\.0\.1:8002/i,
  /https?:\/\/0\.0\.0\.0:8002/i,
];

function bundleFiles(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) return bundleFiles(fullPath);
    return /\.(?:html|js|json)$/i.test(entry.name) ? [fullPath] : [];
  });
}

export function validateMobileBundle({ distDir, expectedApiBase }) {
  const errors = [];
  const expected = String(expectedApiBase || '').trim().replace(/\/$/, '');

  if (!expected) errors.push('VITE_API_BASE is missing from .env.release.');
  if (!fs.existsSync(distDir)) errors.push(`Mobile bundle directory does not exist: ${distDir}`);
  if (errors.length) return { ok: false, errors };

  const text = bundleFiles(distDir)
    .map((file) => fs.readFileSync(file, 'utf8'))
    .join('\n');

  if (LOCAL_API_PATTERNS.some((pattern) => pattern.test(text))) {
    errors.push('Mobile bundle contains a localhost API URL. Build with --mode release.');
  }
  if (!text.includes(expected)) {
    errors.push(`Mobile bundle does not contain the release API URL: ${expected}`);
  }

  return { ok: errors.length === 0, errors };
}

function run() {
  const scriptDir = path.dirname(fileURLToPath(import.meta.url));
  const frontendDir = path.resolve(scriptDir, '..');
  const envPath = path.join(frontendDir, '.env.release');
  const env = fs.existsSync(envPath) ? parseEnvFile(fs.readFileSync(envPath, 'utf8')) : {};
  const result = validateMobileBundle({
    distDir: path.join(frontendDir, 'dist'),
    expectedApiBase: env.VITE_API_BASE,
  });

  if (!result.ok) {
    console.error(result.errors.join('\n'));
    process.exitCode = 1;
    return;
  }
  console.log(`Mobile bundle API verified: ${env.VITE_API_BASE}`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) run();
