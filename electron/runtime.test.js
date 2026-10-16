'use strict';
/**
 * Checks for runtime.js — the startup decisions that cannot be exercised by
 * launching the app (writable dirs, port reuse vs spawn, identity probe,
 * fallback when a portable drive is read-only).
 *
 *   node --test runtime.test.js
 */

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const os = require('os');
const path = require('path');

const {
  apiBaseFor,
  chooseFreePort,
  isPortFree,
  probeBackend,
  resolveEndpoint,
  resolveRoots,
  stopProcessTree,
  wsUrlFor,
} = require('./runtime');

const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), 'sovereign-test-'));
const always = (value) => () => value;

test('installed build keeps per-user data and never becomes portable', () => {
  const roots = resolveRoots({
    isPackaged: true,
    exePath: 'C:\\Program Files\\SovereignAI\\SovereignAI.exe',
    env: {},
    appDataDir: 'C:\\Users\\me\\AppData\\Roaming',
  });
  assert.equal(roots.portableRoot, null, 'a read-only install dir is not portable');
  assert.equal(roots.dataRoot, path.join('C:\\Users\\me\\AppData\\Roaming', 'SovereignAI'));
  assert.equal(roots.workspaceDir, path.join(roots.dataRoot, 'workspace'));
});

test('a data/ sibling next to the exe switches portable mode on', () => {
  const dir = path.join(tmp(), 'portable');
  fs.mkdirSync(path.join(dir, 'data'), { recursive: true });
  const roots = resolveRoots({
    isPackaged: true,
    exePath: path.join(dir, 'SovereignAI.exe'),
    env: {},
    appDataDir: 'C:\\Users\\me\\AppData\\Roaming',
  });
  assert.equal(roots.portableRoot, dir);
  assert.equal(roots.dataRoot, path.join(dir, 'data'));
  assert.equal(roots.userDataDir, path.join(dir, 'data', 'electron'), 'cache stays on the drive');
  assert.equal(roots.tempDir, path.join(dir, 'data', 'cache', 'temp'));
  assert.equal(roots.fallback, false);
});

test('a non-writable portable dir falls back to the per-user dir', () => {
  const dir = path.join(tmp(), 'portable');
  fs.mkdirSync(path.join(dir, 'data'), { recursive: true });
  const roots = resolveRoots({
    isPackaged: true,
    exePath: path.join(dir, 'SovereignAI.exe'),
    env: {},
    appDataDir: path.join('C:\\Users', 'me', 'AppData', 'Roaming'),
    isWritable: always(false), // e.g. extracted into Program Files
  });
  assert.equal(roots.portableRoot, null);
  assert.equal(roots.fallback, true);
  assert.equal(roots.dataRoot, path.join('C:\\Users', 'me', 'AppData', 'Roaming', 'SovereignAI'));
  assert.equal(roots.tempDir, null, 'the OS temp dir is used when the drive is unusable');
});

test('a portable dir that cannot host caches disables the GPU cache, not the app', () => {
  const dir = path.join(tmp(), 'portable');
  fs.mkdirSync(path.join(dir, 'data'), { recursive: true });
  const roots = resolveRoots({
    isPackaged: true,
    exePath: path.join(dir, 'SovereignAI.exe'),
    env: {},
    appDataDir: path.join(tmp(), 'roaming'), // writable per-user fallback
    isWritable: (p) => !p.startsWith(dir), // only the portable tree is locked down
  });
  assert.equal(roots.fallback, true);
  assert.equal(roots.cacheReady, true, 'per-user dir is usable, so GPU stays on');
});

test('dev run keeps the repo as the data root', () => {
  const repo = tmp();
  const roots = resolveRoots({
    isPackaged: false,
    exePath: null,
    env: {},
    appDataDir: path.join('C:\\Users', 'me', 'AppData', 'Roaming'),
    devRoot: repo,
  });
  assert.equal(roots.dataRoot, repo);
  assert.equal(roots.workspaceDir, path.join(repo, 'workspace'));
});

test('resolveRoots creates every directory it reports as usable', () => {
  const dir = path.join(tmp(), 'portable');
  fs.mkdirSync(path.join(dir, 'data'), { recursive: true });
  const roots = resolveRoots({
    isPackaged: true,
    exePath: path.join(dir, 'SovereignAI.exe'),
    env: {},
    appDataDir: 'C:\\Users\\me\\AppData\\Roaming',
  });
  assert.equal(roots.cacheReady, true);
  assert.ok(fs.existsSync(roots.workspaceDir), 'workspace dir exists');
  assert.ok(fs.existsSync(roots.userDataDir), 'userData dir exists');
  assert.ok(fs.existsSync(roots.tempDir), 'portable TEMP dir exists');
});

test('apiBaseFor/wsUrlFor agree on host and port', () => {
  assert.equal(apiBaseFor(8123), 'http://127.0.0.1:8123');
  assert.equal(wsUrlFor(8123), 'ws://127.0.0.1:8123/ws/metrics');
});

test('port probing reports the truth for a live listener', async () => {
  const net = require('net');
  const server = net.createServer();
  await new Promise((resolve) => server.listen({ port: 0, host: '127.0.0.1' }, resolve));
  const taken = server.address().port;
  assert.equal(await isPortFree(taken), false, 'listening port is not free');
  await new Promise((resolve) => server.close(resolve));
  assert.equal(await isPortFree(taken), true, 'closed port is free again');
});

test('chooseFreePort skips taken ports instead of evicting the holder', async () => {
  const chosen = await chooseFreePort(9000, '127.0.0.1', 5, async (port) => port !== 9000 && port !== 9001);
  assert.equal(chosen, 9002);
  assert.equal(await chooseFreePort(9000, '127.0.0.1', 2, async () => false), null);
});

test('endpoint reuses a healthy SovereignAI before spawning a second one', async () => {
  const dataRoot = tmp();
  let probed = [];
  const endpoint = await resolveEndpoint(dataRoot, {
    probe: async (port) => { probed.push(port); return port === 8000 ? { name: 'SovereignAI Edge', pid: 42 } : null; },
    isFree: async (port) => port === 8001,
  });
  assert.deepEqual(endpoint, { port: 8000, host: '127.0.0.1', reuse: true, info: { name: 'SovereignAI Edge', pid: 42 } });
  assert.equal(probed[0], 8000, 'probes the default port first');
});

test('endpoint falls back to the next free port when 8000 is a foreign process', async () => {
  const dataRoot = tmp();
  const endpoint = await resolveEndpoint(dataRoot, {
    probe: async () => null, // answers, but is not us (or nothing answers)
    isFree: async (port) => port === 8001,
  });
  assert.equal(endpoint.port, 8001);
  assert.equal(endpoint.reuse, false);
  assert.equal(endpoint.moved, true);
});

test('endpoint honors SOVEREIGN_API_PORT as the preferred port', async () => {
  const endpoint = await resolveEndpoint(tmp(), {
    env: { SOVEREIGN_API_PORT: '9123' },
    probe: async () => null,
    isFree: async (port) => port === 9123,
  });
  assert.equal(endpoint.port, 9123);
  assert.equal(endpoint.moved, false);
});

test('endpoint reuses the port recorded by the previous run', async () => {
  const dataRoot = tmp();
  fs.mkdirSync(path.join(dataRoot, 'workspace'), { recursive: true });
  fs.writeFileSync(
    path.join(dataRoot, 'workspace', 'backend.json'),
    JSON.stringify({ pid: 7, port: 8300 })
  );
  const probed = [];
  const endpoint = await resolveEndpoint(dataRoot, {
    probe: async (port) => { probed.push(port); return port === 8300 ? { name: 'SovereignAI Edge' } : null; },
    isFree: async () => false, // every port busy: reuse is the only way through
  });
  assert.equal(endpoint.port, 8300);
  assert.equal(endpoint.reuse, true);
  assert.equal(probed[0], 8300, 'the remembered port is probed before the default');
});

test('endpoint reports no port when everything is taken by others', async () => {
  const endpoint = await resolveEndpoint(tmp(), { probe: async () => null, isFree: async () => false });
  assert.equal(endpoint.port, null);
  assert.equal(endpoint.reuse, false);
});

test('probeBackend rejects an unrelated app answering on the port', async () => {
  const http = require('http');
  const server = http.createServer((req, res) => {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'healthy', name: 'Some Other App' }));
  });
  await new Promise((resolve) => server.listen({ port: 0, host: '127.0.0.1' }, resolve));
  const port = server.address().port;
  try {
    assert.equal(await probeBackend(port), null, 'identity mismatch is not adopted');
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});

test('probeBackend accepts a matching SovereignAI identity', async () => {
  const http = require('http');
  const server = http.createServer((req, res) => {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'healthy', name: 'SovereignAI Edge', pid: process.pid }));
  });
  await new Promise((resolve) => server.listen({ port: 0, host: '127.0.0.1' }, resolve));
  const port = server.address().port;
  try {
    const info = await probeBackend(port);
    assert.equal(info && info.name, 'SovereignAI Edge');
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});

test('stopProcessTree tolerates a pid that is already gone', () => {
  assert.doesNotThrow(() => stopProcessTree(0));
  assert.doesNotThrow(() => stopProcessTree(undefined));
});
