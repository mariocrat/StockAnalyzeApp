// Scoped synchronous fixture for the two Node release-check test files only.
import nodeTest, { after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
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
import { fileURLToPath, pathToFileURL } from 'node:url';
import { syncBuiltinESMExports } from 'node:module';

const helperFile = fileURLToPath(import.meta.url);
const frontend = path.resolve(path.dirname(helperFile), '..');
const native = {
  mkdtemp: fs.mkdtempSync, mkdir: fs.mkdirSync, read: fs.readFileSync,
  write: fs.writeFileSync, rm: fs.rmSync, exists: fs.existsSync,
  realpath: fs.realpathSync, chdir: process.chdir, spawn: childProcess.spawnSync,
};
// Read only this fixed source allowlist, before any testcase or nested fixture.
const sources = new Map(['package.json', '.env.example', '.env.release.example',
  'scripts/validate-release-env.js', 'scripts/validate-mobile-bundle.js',
  'scripts/owner-release-report.js', 'scripts/release-test-isolation.mjs']
  .map((relative) => [relative, native.read(path.join(frontend, relative))]));
const roots = new Set();
let active;
let suiteRegistered = false;

function replaceEnvironment(values) {
  for (const key of Object.keys(process.env)) delete process.env[key];
  Object.assign(process.env, values);
}

function cleanEnvironment(root) {
  const values = {};
  for (const key of ['SystemRoot', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'SYSTEMDRIVE']) {
    if (process.env[key] !== undefined) values[key] = process.env[key];
  }
  return {
    ...values,
    HOME: path.join(root, 'home'), USERPROFILE: path.join(root, 'home'),
    APPDATA: path.join(root, 'config'), LOCALAPPDATA: path.join(root, 'config'),
    TEMP: path.join(root, 'tmp'), TMP: path.join(root, 'tmp'), TMPDIR: path.join(root, 'tmp'),
    ALPHAMATE_FRONTEND_ENV_FILE: path.join(root, '.env'),
  };
}

function within(root, target) {
  const relative = path.relative(root, target);
  return relative === '' || (!path.isAbsolute(relative) && relative !== '..' && !relative.startsWith(`..${path.sep}`));
}

function installGuards(root) {
  const patches = [];
  const violations = [];
  const acknowledged = new Set();
  const deny = (kind) => {
    violations.push(kind);
    throw new Error(`Node release isolation blocked: ${kind}`);
  };
  function owned(raw) {
    if (raw instanceof URL) raw = fileURLToPath(raw);
    if (Buffer.isBuffer(raw)) raw = raw.toString();
    if (typeof raw !== 'string') return deny('file-descriptor');
    const target = path.resolve(raw);
    // Reject before even querying metadata for host/private paths.
    if (!within(root, target)) return deny('filesystem');
    let ancestor = target;
    while (!native.exists(ancestor)) ancestor = path.dirname(ancestor);
    if (!within(root, native.realpath(ancestor))) return deny('filesystem');
    return target;
  }
  function patch(object, key, value) {
    if (typeof object[key] !== 'function') return;
    patches.push([object, key, Object.getOwnPropertyDescriptor(object, key)]);
    object[key] = value;
  }
  for (const name of ['readFileSync', 'existsSync', 'readdirSync', 'statSync', 'lstatSync',
    'accessSync', 'realpathSync', 'writeFileSync', 'appendFileSync', 'mkdirSync', 'mkdtempSync',
    'rmSync', 'unlinkSync', 'rmdirSync', 'chmodSync', 'utimesSync', 'truncateSync', 'openSync']) {
    const original = fs[name];
    patch(fs, name, (target, ...args) => original(owned(target), ...args));
  }
  for (const name of ['renameSync', 'copyFileSync', 'cpSync']) {
    const original = fs[name];
    patch(fs, name, (source, target, ...args) => original(owned(source), owned(target), ...args));
  }
  // These fixtures need no links, asynchronous filesystem or file watchers.
  for (const name of ['linkSync', 'symlinkSync', 'readlinkSync', 'watch', 'watchFile',
    'createReadStream', 'createWriteStream', 'open', 'readFile', 'writeFile', 'appendFile',
    'mkdir', 'mkdtemp', 'rm', 'unlink', 'rmdir', 'rename', 'copyFile', 'cp', 'link', 'symlink']) {
    patch(fs, name, () => deny('filesystem-api'));
  }
  for (const name of Object.keys(fs.promises)) patch(fs.promises, name, () => deny('filesystem-api'));
  for (const [object, names] of [
    [net.Socket.prototype, ['connect']], [net.Server.prototype, ['listen']],
    [tls, ['connect']], [http, ['request', 'get']], [https, ['request', 'get']],
    [http2, ['connect']], [dgram, ['createSocket']], [globalThis, ['fetch', 'WebSocket']],
    [dns, Object.keys(dns).filter((name) => /^(lookup|resolve|reverse)/.test(name))],
    [dns.promises, Object.keys(dns.promises).filter((name) => /^(lookup|resolve|reverse)/.test(name))],
  ]) {
    for (const name of names) patch(object, name, () => deny('network'));
  }
  for (const name of ['spawn', 'spawnSync', 'exec', 'execSync', 'execFile', 'execFileSync', 'fork']) {
    patch(childProcess, name, () => deny('subprocess'));
  }
  patch(process, 'chdir', (directory) => native.chdir(owned(directory)));
  syncBuiltinESMExports();
  return {
    owned,
    violations,
    get unexpected() { return violations.filter((_, index) => !acknowledged.has(index)); },
    expectBlocked(kind, operation) {
      const before = violations.length;
      assert.throws(operation, /Node release isolation blocked:/);
      assert.deepEqual(violations.slice(before), [kind]);
      acknowledged.add(before);
    },
    restore() {
      for (const [object, key, descriptor] of patches.reverse()) Object.defineProperty(object, key, descriptor);
      syncBuiltinESMExports();
      for (const [object, key, descriptor] of patches) {
        assert.deepEqual(Object.getOwnPropertyDescriptor(object, key), descriptor);
      }
    },
  };
}

export function withWorkspace(body, { setup = () => {} } = {}) {
  const previous = { env: { ...process.env }, cwd: process.cwd(), active };
  const temporaryBase = native.realpath(os.tmpdir());
  const root = native.mkdtemp(path.join(temporaryBase, 'stockboda-node-release-'));
  roots.add(root);
  let guard;
  try {
    for (const directory of ['scripts', 'home', 'config', 'tmp']) native.mkdir(path.join(root, directory));
    // Exact tracked source/templates only. Never copy .env, credentials or host HOME.
    for (const [relative, content] of sources) native.write(path.join(root, relative), content);
    for (const name of ['.env', '.env.release']) native.write(path.join(root, name), 'VITE_APP_NAME=SyntheticFileName\n');
    replaceEnvironment(cleanEnvironment(root));
    native.chdir(root);
    guard = installGuards(root);
    active = { root, ...guard };
    setup(active);
    const result = body(active);
    assert.equal(result?.then, undefined, 'release fixtures must stay synchronous');
    return result;
  } finally {
    try {
      guard?.restore();
    } finally {
      active = previous.active;
      native.chdir(previous.cwd);
      replaceEnvironment(previous.env);
      native.rm(root, { recursive: true, force: true });
      roots.delete(root);
      assert.equal(native.exists(root), false);
      assert.equal(process.cwd(), previous.cwd);
      assert.deepEqual({ ...process.env }, previous.env);
      assert.deepEqual(guard?.unexpected ?? [], [], 'unacknowledged boundary violation');
    }
  }
}

export function test(name, body) {
  if (!suiteRegistered) {
    after(() => assert.equal(roots.size, 0, 'test-owned temporary roots remain'));
    suiteRegistered = true;
  }
  return nodeTest(name, { concurrency: false }, () => withWorkspace(body));
}

export function ownedTempDir(prefix) {
  assert.ok(active, 'test workspace required');
  return fs.mkdtempSync(path.join(active.root, 'tmp', prefix));
}

export function spawnSync(executable, args, options = {}) {
  assert.ok(active, 'test workspace required');
  assert.equal(executable, process.execPath, 'only the Node test child is authorized');
  assert.equal(options.cwd, active.root);
  assert.equal(options.encoding, 'utf8');
  assert.equal(args.length, args[0] === '-e' ? 2 : 1, 'no extra child permission or preload flags');
  const script = args[0] === '-e' ? null : active.owned(args[0]);
  assert.ok(script === null || ['validate-release-env.js', 'owner-release-report.js']
    .some((name) => script === path.join(active.root, 'scripts', name)));
  const env = cleanEnvironment(active.root);
  // Explicit synthetic settings only; no spread of host/process.env into the child.
  for (const [key, value] of Object.entries(options.env ?? {})) {
    assert.match(key, /^(VITE_|ALPHAMATE_ANDROID_)/);
    env[key] = value;
  }
  if (env.ALPHAMATE_ANDROID_KEYSTORE_FILE) active.owned(env.ALPHAMATE_ANDROID_KEYSTORE_FILE);
  const childEnvFile = path.join(ownedTempDir('child-env-'), '.env.release');
  fs.writeFileSync(childEnvFile, Object.entries(options.env ?? {}).map(([key, value]) => `${key}=${value}`).join('\n'));
  env.ALPHAMATE_FRONTEND_ENV_FILE = childEnvFile;
  env.STOCKBODA_NODE_TEST_CHILD_ROOT = active.root;
  return native.spawn(executable, [
    '--permission', `--allow-fs-read=${active.root}`, `--allow-fs-write=${active.root}`,
    '--import', pathToFileURL(path.join(active.root, 'scripts/release-test-isolation.mjs')).href, ...args,
  ], { cwd: active.root, env, encoding: 'utf8', timeout: 15000, windowsHide: true });
}

export function checkFailureCleanup() {
  for (const outcome of ['success', 'assertion', 'setup']) {
    const before = { env: { ...process.env }, cwd: process.cwd(), read: fs.readFileSync, spawn: childProcess.spawnSync };
    let root;
    const setup = (workspace) => {
      root = workspace.root;
      fs.writeFileSync(path.join(root, 'setup-fixture'), 'synthetic');
      process.env.SYNTHETIC_SETUP = outcome;
      if (outcome === 'setup') throw new Error('synthetic setup failure');
    };
    const body = () => {
      fs.writeFileSync(path.join(ownedTempDir('body-'), 'fixture'), 'synthetic');
      process.env.SYNTHETIC_BODY = outcome;
      process.chdir(path.join(root, 'tmp'));
      fs.readFileSync = () => 'synthetic module mutation';
      if (outcome === 'assertion') assert.fail('synthetic assertion failure');
    };
    if (outcome === 'success') withWorkspace(body, { setup });
    else assert.throws(() => withWorkspace(body, { setup }), new RegExp(`synthetic ${outcome} failure`));
    assert.equal(native.exists(root), false);
    assert.equal(process.cwd(), before.cwd);
    assert.deepEqual({ ...process.env }, before.env);
    assert.equal(fs.readFileSync, before.read);
    assert.equal(childProcess.spawnSync, before.spawn);
  }
}

if (process.env.STOCKBODA_NODE_TEST_CHILD_ROOT) {
  const root = native.realpath(process.env.STOCKBODA_NODE_TEST_CHILD_ROOT);
  assert.equal(process.cwd(), root);
  const guard = installGuards(root);
  process.on('exit', () => {
    if (guard.violations.length) process.exitCode = 1;
  });
}
