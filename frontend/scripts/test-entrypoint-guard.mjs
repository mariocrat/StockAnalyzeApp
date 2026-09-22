// Cooperative test boundary plus Node's native filesystem permissions.
// Only copied source and disposable fixtures are visible to a test process.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import childProcess from 'node:child_process';
import net from 'node:net';
import tls from 'node:tls';
import http from 'node:http';
import https from 'node:https';
import http2 from 'node:http2';
import dns from 'node:dns';
import dgram from 'node:dgram';
import { createHash } from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { syncBuiltinESMExports } from 'node:module';

const native = {
  exists: fs.existsSync, realpath: fs.realpathSync, read: fs.readFileSync,
  chdir: process.chdir, spawn: childProcess.spawnSync,
};
const root = native.realpath(process.cwd());
const config = JSON.parse(native.read(path.join(root, '.node-test-config.json'), 'utf8'));
assert.equal(process.env.STOCKBODA_NODE_COORDINATOR_ROOT, root);
assert.equal(process.env.HOME, path.join(root, 'home'));
assert.equal(process.env.TEMP, path.join(root, 'tmp'));
const environment = { ...process.env };
const patches = [];
const violations = [];
let finished;

function deny(kind) {
  violations.push(kind);
  throw new Error(`Node entrypoint isolation blocked: ${kind}`);
}

function within(base, target) {
  const relative = path.relative(base, target);
  return relative === '' || (!path.isAbsolute(relative) && relative !== '..' && !relative.startsWith(`..${path.sep}`));
}

function owned(raw) {
  if (raw instanceof URL) raw = fileURLToPath(raw);
  if (Buffer.isBuffer(raw)) raw = raw.toString();
  if (typeof raw !== 'string') return deny('file-descriptor');
  const target = path.resolve(raw);
  // Lexical rejection precedes even a metadata read outside the workspace.
  if (!within(root, target)) return deny('filesystem');
  let ancestor = target;
  while (!native.exists(ancestor)) ancestor = path.dirname(ancestor);
  if (!within(root, native.realpath(ancestor))) return deny('filesystem');
  return target;
}

function patch(object, name, value) {
  if (typeof object[name] !== 'function') return;
  patches.push([object, name, Object.getOwnPropertyDescriptor(object, name)]);
  object[name] = value;
}

for (const suffix of ['', 'Sync']) {
  for (const name of ['readFile', 'writeFile', 'appendFile', 'access', 'stat', 'lstat', 'realpath',
    'readdir', 'mkdir', 'mkdtemp', 'rm', 'rmdir', 'unlink', 'chmod', 'utimes', 'truncate', 'open', 'exists']) {
    const key = name + suffix;
    const original = fs[key];
    patch(fs, key, (target, ...args) => original(owned(target), ...args));
  }
  for (const name of ['rename', 'copyFile', 'cp']) {
    const key = name + suffix;
    const original = fs[key];
    patch(fs, key, (source, target, ...args) => original(owned(source), owned(target), ...args));
  }
  for (const name of ['link', 'symlink', 'readlink']) patch(fs, name + suffix, () => deny('filesystem-api'));
}
for (const name of Object.keys(fs.promises)) {
  const original = fs.promises[name];
  if (['rename', 'copyFile', 'cp'].includes(name)) {
    patch(fs.promises, name, (source, target, ...args) => original(owned(source), owned(target), ...args));
  } else if (['link', 'symlink', 'readlink', 'watch', 'open'].includes(name)) {
    patch(fs.promises, name, () => deny('filesystem-api'));
  } else {
    patch(fs.promises, name, (target, ...args) => original(owned(target), ...args));
  }
}
for (const name of ['watch', 'watchFile', 'createReadStream', 'createWriteStream']) {
  patch(fs, name, () => deny('filesystem-api'));
}
for (const [object, names] of [
  [net.Socket.prototype, ['connect']], [net.Server.prototype, ['listen']], [tls, ['connect']],
  [http, ['request', 'get']], [https, ['request', 'get']], [http2, ['connect']],
  [dgram, ['createSocket']], [globalThis, ['fetch', 'WebSocket']],
  [dns, Object.keys(dns).filter(name => /^(lookup|resolve|reverse)/.test(name))],
  [dns.promises, Object.keys(dns.promises).filter(name => /^(lookup|resolve|reverse)/.test(name))],
]) for (const name of names) patch(object, name, () => deny('network'));
for (const name of ['spawn', 'spawnSync', 'exec', 'execSync', 'execFile', 'execFileSync', 'fork']) {
  patch(childProcess, name, () => deny('subprocess'));
}

// Preserve only the already-reviewed release helper's exact constrained launch.
// No shell, other executable, other preload, or broader permission is accepted.
if (config.profile === 'release') {
  patch(childProcess, 'spawnSync', (executable, args, options = {}) => {
    const cwd = owned(options.cwd);
    const env = options.env ?? {};
    const expected = ['--permission', `--allow-fs-read=${cwd}`, `--allow-fs-write=${cwd}`,
      '--import', pathToFileURL(path.join(cwd, 'scripts/release-test-isolation.mjs')).href];
    const script = args?.[5];
    const evalHash = script === '-e' && typeof args[6] === 'string'
      ? createHash('sha256').update(args[6]).digest('hex') : null;
    const validScript = args?.length === 6 && ['validate-release-env.js', 'owner-release-report.js']
      .some(name => script === path.join(cwd, 'scripts', name));
    const validEval = args?.length === 7 && config.release_eval_sha256.includes(evalHash);
    const envKeys = Object.keys(env);
    if (executable !== process.execPath || !Array.isArray(args) ||
        !expected.every((value, index) => args[index] === value) || !(validScript || validEval) ||
        !within(path.join(root, 'tmp'), cwd) || env.STOCKBODA_NODE_TEST_CHILD_ROOT !== cwd ||
        options.encoding !== 'utf8' || options.timeout !== 15000 || options.windowsHide !== true ||
        Object.keys(options).some(key => !['cwd', 'env', 'encoding', 'timeout', 'windowsHide'].includes(key)) ||
        envKeys.some(key => !/^(SystemRoot|SYSTEMROOT|WINDIR|COMSPEC|SYSTEMDRIVE|HOME|USERPROFILE|APPDATA|LOCALAPPDATA|TEMP|TMP|TMPDIR|ALPHAMATE_FRONTEND_ENV_FILE|STOCKBODA_NODE_TEST_CHILD_ROOT|VITE_\w+|ALPHAMATE_ANDROID_\w+)$/.test(key))) {
      return deny('subprocess');
    }
    for (const key of ['HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'TEMP', 'TMP', 'TMPDIR',
      'ALPHAMATE_FRONTEND_ENV_FILE', 'ALPHAMATE_ANDROID_KEYSTORE_FILE']) {
      if (env[key] !== undefined && !within(cwd, owned(env[key]))) return deny('subprocess');
    }
    return native.spawn(executable, args, options);
  });
}
patch(process, 'chdir', directory => native.chdir(owned(directory)));
syncBuiltinESMExports();

export function finishGuard() {
  if (finished) return finished;
  let patchesRestored = false;
  try {
    for (const [object, name, descriptor] of [...patches].reverse()) Object.defineProperty(object, name, descriptor);
    syncBuiltinESMExports();
    // Repeated patches on spawnSync restore the first (native) descriptor.
    const checked = new Map();
    for (const [object, name, descriptor] of patches) {
      if (!checked.has(object)) checked.set(object, new Map());
      if (!checked.get(object).has(name)) checked.get(object).set(name, descriptor);
    }
    for (const [object, properties] of checked) {
      for (const [name, descriptor] of properties) assert.deepEqual(Object.getOwnPropertyDescriptor(object, name), descriptor);
    }
    patchesRestored = true;
  } finally {
    native.chdir(root);
    for (const key of Object.keys(process.env)) delete process.env[key];
    Object.assign(process.env, environment);
  }
  finished = { violations: [...violations], unexpected: violations.length, patches_restored: patchesRestored,
    restored: process.cwd() === root && JSON.stringify({ ...process.env }) === JSON.stringify(environment),
    module_state: 'disposable process' };
  return finished;
}

export const entrypoint = Object.freeze({ name: config.name, file: config.file });
