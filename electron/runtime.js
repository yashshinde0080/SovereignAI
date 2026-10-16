'use strict';
/**
 * Runtime path + backend-address helpers for the Electron shell.
 *
 * Deliberately free of any `electron` import (the caller passes `app` values in)
 * so this file is unit-testable with plain `node --test` — see runtime.test.js.
 * The desktop shell cannot be launched in CI, and these are exactly the pieces
 * that decide whether the app starts at all (writable dirs, free port,
 * "is that port ours").
 */

const fs = require('fs');
const path = require('path');
const net = require('net');

// Must match backend settings.app_name: a launcher may only adopt a server that
// answers /health with this name.
const APP_IDENTITY = 'SovereignAI Edge';
const STATE_FILENAME = 'backend.json';
const DEFAULT_PORT = 8000;
const PORT_SCAN_LIMIT = 20;

/** Create a directory and prove it is writable. Never throws. */
function ensureWritableDir(dir) {
  try {
    fs.mkdirSync(dir, { recursive: true });
    fs.accessSync(dir, fs.constants.W_OK);
    return true;
  } catch (err) {
    console.warn(`Directory not writable: ${dir} (${err.message})`);
    return false;
  }
}

/**
 * Where the app keeps writable state.
 *
 * Portable builds keep everything next to the exe (nothing outside the zip is
 * touched). If that directory is not writable — a read-only drive, or a
 * portable folder dropped inside Program Files — fall back to the per-user
 * directory instead of starting with a broken cache.
 */
function resolveRoots({ isPackaged, exePath, env = {}, appDataDir, devRoot = null, isWritable = ensureWritableDir }) {
  // Dev keeps the repo as its data root (that is what app/config.py does when
  // it is not frozen), so a dev run and `python main.py` share one workspace.
  if (!isPackaged && devRoot) {
    const userRoot = path.join(appDataDir, 'SovereignAI');
    isWritable(path.join(devRoot, 'workspace')); // create it, like the app expects
    return {
      portableRoot: null,
      dataRoot: devRoot,
      workspaceDir: path.join(devRoot, 'workspace'),
      userDataDir: userRoot,
      tempDir: null,
      fallback: false,
      cacheReady: isWritable(userRoot),
    };
  }

  const exeDir = isPackaged && exePath ? path.dirname(exePath) : null;
  const portableMarked = !isPackaged
    ? false
    : Boolean(
        env.PORTABLE_EXECUTABLE_DIR
        || env.SOVEREIGN_PORTABLE === '1'
        || (exeDir && fs.existsSync(path.join(exeDir, 'data')))
      );
  const portableRoot = portableMarked ? (env.PORTABLE_EXECUTABLE_DIR || exeDir) : null;

  if (portableRoot) {
    const root = path.join(portableRoot, 'data');
    const dirs = {
      portableRoot,
      dataRoot: root,
      workspaceDir: path.join(root, 'workspace'),
      userDataDir: path.join(root, 'electron'),
      tempDir: path.join(root, 'cache', 'temp'),
      fallback: false,
    };
    // Everything Chromium and the backend need, created and proven writable
    // before a window exists (a missing/read-only userData or TEMP is what
    // produced "Unable to create cache"/"Access is denied").
    dirs.cacheReady = isWritable(dirs.workspaceDir)
      && isWritable(dirs.userDataDir)
      && isWritable(dirs.tempDir);
    if (dirs.cacheReady) return dirs;

    console.warn(
      `Portable data directory is not writable (${root}); using the per-user ` +
      `directory instead so the app can still start. Move the folder to a ` +
      `writable location (not Program Files) to stay portable.`
    );
  }

  const userRoot = path.join(appDataDir, 'SovereignAI');
  return {
    portableRoot: null,
    dataRoot: userRoot,
    workspaceDir: path.join(userRoot, 'workspace'),
    userDataDir: userRoot,
    tempDir: null, // OS temp
    fallback: Boolean(portableRoot),
    cacheReady: isWritable(userRoot),
  };
}

const stateFilePath = (dataRoot) => path.join(dataRoot, 'workspace', STATE_FILENAME);

/** Last backend this install started, or null. Stale entries are harmless:
 *  the caller still has to prove health + identity before reusing the port. */
function readState(dataRoot) {
  try {
    const data = JSON.parse(fs.readFileSync(stateFilePath(dataRoot), 'utf8'));
    return data && typeof data === 'object' ? data : null;
  } catch (err) {
    return null;
  }
}

const apiBaseFor = (port, host = '127.0.0.1') => `http://${host}:${port}`;
const wsUrlFor = (port, host = '127.0.0.1') => `ws://${host}:${port}/ws/metrics`;

/** True when a server could bind `port` right now. */
function isPortFree(port, host = '127.0.0.1') {
  return new Promise((resolve) => {
    const server = net.createServer();
    const done = (free) => {
      try { server.close(); } catch (err) { /* already closed */ }
      resolve(free);
    };
    server.once('error', () => done(false));
    server.once('listening', () => server.close(() => resolve(true)));
    server.listen({ port, host, exclusive: true });
  });
}

/** The next free port at or above `preferred`, or null. Never evicts a holder. */
async function chooseFreePort(preferred, host = '127.0.0.1', limit = PORT_SCAN_LIMIT, isFree = isPortFree) {
  for (let port = preferred; port <= preferred + limit && port < 65536; port++) {
    if (await isFree(port, host)) return port;
  }
  return null;
}

/**
 * Ask who is listening on `port`. Returns /health's body only when it is a
 * healthy SovereignAI backend — an unrelated app that happens to answer 200 on
 * that port must never be adopted (or worse, terminated on quit).
 */
async function probeBackend(port, host = '127.0.0.1', timeoutMs = 2000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${apiBaseFor(port, host)}/health`, { signal: controller.signal });
    if (!res.ok) return null;
    const body = await res.json();
    return body && body.name === APP_IDENTITY && body.status === 'healthy' ? body : null;
  } catch (err) {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Pick the backend endpoint. Reuse before spawn, always: if our own backend is
 * already listening (a previous run the user force-quit, or a second launch),
 * a second copy must not be started on another port — two backends sharing one
 * SQLite file is what produced "database is locked".
 *
 * Resolution order: SOVEREIGN_API_PORT -> the port we used last -> 8000, probed
 * for a healthy SovereignAI; then the first free port at or above the preferred
 * one. Returns { port: null } when every candidate is taken by something else.
 */
async function resolveEndpoint(dataRoot, {
  host = '127.0.0.1',
  limit = PORT_SCAN_LIMIT,
  env = process.env,
  probe = probeBackend,
  isFree = isPortFree,
} = {}) {
  const state = readState(dataRoot);
  const envPort = Number(env.SOVEREIGN_API_PORT) || null;
  const preferred = envPort || (Number(state && state.port) || null) || DEFAULT_PORT;

  const candidates = [...new Set([preferred, Number(state && state.port), DEFAULT_PORT].filter(Boolean))];
  for (const port of candidates) {
    const info = await probe(port, host);
    if (info) return { port, host, reuse: true, info };
  }

  const port = await chooseFreePort(preferred, host, limit, isFree);
  if (port === null) return { port: null, host, reuse: false, info: null };
  return { port, host, reuse: false, moved: port !== preferred, info: null };
}

/** Stop a process and its children (Windows: taskkill /T). Kills nothing else. */
function stopProcessTree(pid, { force = true, platform = process.platform } = {}) {
  if (!pid) return;
  if (platform === 'win32') {
    const args = ['/pid', String(pid), '/T'];
    if (force) args.push('/F');
    try {
      require('child_process').spawn('taskkill', args, { windowsHide: true });
    } catch (err) {
      console.warn('taskkill failed:', err.message);
    }
    return;
  }
  try {
    process.kill(pid, force ? 'SIGKILL' : 'SIGTERM');
  } catch (err) {
    console.warn('process.kill failed:', err.message);
  }
}

module.exports = {
  APP_IDENTITY,
  DEFAULT_PORT,
  PORT_SCAN_LIMIT,
  STATE_FILENAME,
  apiBaseFor,
  chooseFreePort,
  ensureWritableDir,
  isPortFree,
  probeBackend,
  readState,
  resolveEndpoint,
  resolveRoots,
  stateFilePath,
  stopProcessTree,
  wsUrlFor,
};
