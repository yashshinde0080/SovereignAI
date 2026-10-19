const { app, BrowserWindow, ipcMain, dialog, protocol, net, Notification } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const { createMenu } = require('./menu');
const { createTray } = require('./tray');
const {
  DEFAULT_PORT,
  apiBaseFor,
  ensureWritableDir,
  probeBackend,
  resolveEndpoint,
  resolveRoots,
  stopProcessTree,
  wsUrlFor,
} = require('./runtime');

let mainWindow;
let backendProcess;
let backendStarting = false;
// Only a backend this process spawned is ever stopped — an adopted one belongs
// to another instance.
let backendOwned = false;
let tray;
// Resolved before the window exists: the renderer gets the port through
// additionalArguments, so it must be known at BrowserWindow construction time.
let backendPort = null;
let quitting = false;

const FRONTEND_PORT = 3000;
const BACKEND_HEALTH_TIMEOUT_MS = 120000;
const BACKEND_STOP_TIMEOUT_MS = 15000;

const isDev = !app.isPackaged;

// ── Writable directories (before anything reads a path) ─────────────────────
// A cached profile path that cannot be created is what produced Chromium's
// "Unable to create cache" / "Access is denied" and "Gpu Cache Creation
// failed": the install directory (Program Files) is read-only, so userData,
// session data and the GPU shader cache all have to live in a writable place.
const roots = resolveRoots({
  isPackaged: app.isPackaged,
  exePath: app.isPackaged ? app.getPath('exe') : null,
  env: process.env,
  appDataDir: app.getPath('appData'),
  devRoot: path.join(__dirname, '..'),
});

const cacheReady = roots.cacheReady;

// Stale Chromium profile locks from a previous force-kill make the profile look
// "in use" and silently degrade the session (cache/session creation failures).
// Safe to clear here: requestSingleInstanceLock() below proves no other
// instance of this app is running.
app.setPath('userData', roots.userDataDir);

// Clear profile locks only after this process holds the single-instance
// lock. Clearing the files only when the lock owner is dead is correct.
for (const lock of ['SingletonLock', 'SingletonSocket', 'SingletonCookie', 'lockfile']) {
  try {
    fs.rmSync(path.join(roots.userDataDir, lock), { force: true });
  } catch (err) {
    console.warn(`Could not clear stale profile lock ${lock}:`, err.message);
  }
}
if (roots.tempDir && cacheReady) app.setPath('temp', roots.tempDir);

// GPU is only disabled when it genuinely cannot work (documented fallback):
// an explicit opt-out, or a cache directory that could not be created. The
// shader disk cache is the part that needs a writable userData dir, so dropping
// just that keeps hardware acceleration on everywhere it can be.
if (process.env.SOVEREIGN_DISABLE_GPU === '1' || !cacheReady) {
  console.warn('Disabling GPU acceleration (no writable cache directory).');
  app.commandLine.appendSwitch('disable-gpu');
  app.commandLine.appendSwitch('disable-gpu-shader-disk-cache');
  app.commandLine.appendSwitch('disable-software-rasterizer');
}

function workspaceDir() {
  return roots.workspaceDir;
}

// Read a boolean general setting straight from the settings DB files, before
// the backend boots (auto_start_backend) or without waiting for it
// (minimize_to_tray). Zero-dep: values are stored as plain JSON text in the
// SQLite file and its WAL, so a byte scan finds them. Defaults on any error.
function readGeneralFlag(key, fallback) {
  try {
    const base = path.join(workspaceDir(), 'database', 'sovereign_settings.db');
    for (const f of [base, base + '-wal']) {
      if (!fs.existsSync(f)) continue;
      const text = fs.readFileSync(f, 'latin1');
      const m = text.match(new RegExp('"' + key + '":(true|false)'));
      if (m) return m[1] === 'true';
    }
  } catch (e) {
    console.warn('Could not read setting', key, e.message);
  }
  return fallback;
}

function frontendDir() {
  return isDev
    ? path.join(__dirname, '..', 'frontend', 'out')
    : path.join(process.resourcesPath, 'frontend');
}

function backendDir() {
  return isDev
    ? path.join(__dirname, '..', 'backend')
    : path.join(process.resourcesPath, 'backend');
}

// Packaged: a self-contained PyInstaller build (no system Python, no venv).
// Dev: the repo venv, falling back to whatever python is on PATH.
function resolveBackendCommand() {
  if (!isDev) {
    const exe = path.join(backendDir(), 'SovereignAIBackend.exe');
    if (!fs.existsSync(exe)) {
      throw new Error(`Packaged backend not found at ${exe}`);
    }
    return { cmd: exe, args: [] };
  }

  const venvPython = process.platform === 'win32'
    ? path.join(backendDir(), '.venv', 'Scripts', 'python.exe')
    : path.join(backendDir(), '.venv', 'bin', 'python');

  const python = fs.existsSync(venvPython)
    ? venvPython
    : (process.platform === 'win32' ? 'python' : 'python3');

  return { cmd: python, args: ['main.py'] };
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Wait for a healthy SovereignAI that answers on `port`. Identity-checked: a
// foreign process on the port must not read as "our backend is up".
async function waitForBackend(port, timeoutMs = BACKEND_HEALTH_TIMEOUT_MS) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await probeBackend(port)) return true;
    if (!backendProcess && !backendStarting) return false; // died during startup
    await sleep(500);
  }
  return false;
}

async function startBackend() {
  if (backendProcess || backendStarting) return; // never spawn twice
  backendStarting = true;

  try {
    const { cmd, args } = resolveBackendCommand();
    const dir = backendDir();
    const fullArgs = [...args, '--host', '127.0.0.1', '--port', String(backendPort)];

    console.log('Starting backend:', cmd, fullArgs.join(' '));
    // Portable: redirect every temp/cache/config path (and HF_HOME) onto the
    // drive so nothing leaks to the host. Directories were created above.
    let portableEnv = {};
    if (roots.portableRoot) {
      const cache = path.join(roots.dataRoot, 'cache');
      portableEnv = {
        TEMP: path.join(cache, 'temp'), TMP: path.join(cache, 'temp'),
        HF_HOME: path.join(cache, 'hf'),
        XDG_CACHE_HOME: cache,
        XDG_CONFIG_HOME: path.join(roots.dataRoot, 'config'),
        XDG_DATA_HOME: path.join(roots.dataRoot, 'share'),
      };
      for (const d of [portableEnv.TEMP, portableEnv.HF_HOME, portableEnv.XDG_CONFIG_HOME, portableEnv.XDG_DATA_HOME]) {
        ensureWritableDir(d);
      }
    }
    backendProcess = spawn(cmd, fullArgs, {
      cwd: dir,
      windowsHide: true,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1',
        PYTHONDONTWRITEBYTECODE: '1',
        SOVEREIGN_DATA_ROOT: roots.dataRoot,
        SOVEREIGN_API_PORT: String(backendPort),
        ...portableEnv,
      },
    });
    backendOwned = true;
  } catch (err) {
    console.error('Failed to start backend:', err.message);
    backendStarting = false;
    backendProcess = null;
    throw err;
  }

  backendProcess.stdout.on('data', (d) => console.log(`Backend: ${d}`.trimEnd()));
  backendProcess.stderr.on('data', (d) => console.error(`Backend: ${d}`.trimEnd()));
  backendProcess.on('error', (err) => {
    console.error('Backend spawn error:', err.message);
    backendProcess = null;
    backendStarting = false;
  });
  backendProcess.on('exit', (code) => {
    console.log(`Backend exited with code ${code}`);
    backendProcess = null;
    backendStarting = false;
    backendOwned = false;
  });

  const ok = await waitForBackend(backendPort);
  backendStarting = false;
  return ok;
}

/**
 * Stop the backend this process started, gracefully.
 *
 * Hard-terminating (taskkill /F) skips the server's shutdown: SQLite never
 * closes, the audit write never lands, and the aiosqlite thread dies on a
 * closed event loop. So ask the loopback-only /v1/system/shutdown endpoint
 * first and only force-kill if it does not exit in time.
 */
async function stopBackend({ timeoutMs = BACKEND_STOP_TIMEOUT_MS } = {}) {
  const proc = backendProcess;
  backendProcess = null;
  backendStarting = false;
  if (!proc) return;

  if (!backendOwned) {
    console.log('Backend was reused, not started by this instance — leaving it running.');
    return;
  }
  backendOwned = false;
  console.log('Stopping backend...');

  try {
    await fetch(`${apiBaseFor(backendPort)}/v1/system/shutdown`, {
      method: 'POST',
      signal: AbortSignal.timeout(3000),
    });
  } catch (err) {
    console.warn('Graceful shutdown request failed:', err.message);
  }

  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline && proc.exitCode === null) await sleep(250);

  if (proc.exitCode === null) {
    console.warn('Backend did not exit in time — terminating it.');
    stopProcessTree(proc.pid, { force: true });
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 768,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      // The renderer learns the real backend port here: it can fall back to a
      // free port, so it cannot be baked into the build.
      additionalArguments: [`--sovereign-api-base=${apiBaseFor(backendPort || DEFAULT_PORT)}`],
    },
    icon: path.join(__dirname, 'assets', 'icon.png'),
    titleBarStyle: 'hiddenInset',
    show: false,
  });

  // Paint something immediately; the real UI is swapped in once the backend
  // answers /health (a cold torch import takes a while).
  mainWindow.loadURL(
    'data:text/html;charset=utf-8,' + encodeURIComponent(
      '<body style="background:#12101c;color:#eee;font-family:system-ui;display:flex;' +
      'align-items:center;justify-content:center;height:100vh;margin:0">' +
      '<div style="text-align:center"><h2>SovereignAI</h2><p>Starting local engine…</p></div></body>'
    )
  );

  mainWindow.once('ready-to-show', () => mainWindow.show());

  // minimize_to_tray (general settings, read at startup): hide-to-tray on
  // close vs real quit. Read once at boot — restart applies changes.
  const minimizeToTray = readGeneralFlag('minimize_to_tray', true);
  mainWindow.on('close', (event) => {
    if (app.isQuitting || !minimizeToTray) {
      mainWindow = null;
    } else {
      event.preventDefault();
      mainWindow.hide();
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

async function loadFrontend() {
  if (!mainWindow) return;
  if (isDev && process.env.USE_DEV_SERVER === 'true') {
    await mainWindow.loadURL(`http://localhost:${FRONTEND_PORT}`);
  } else {
    await mainWindow.loadURL('app://-/');
  }
  if (isDev) mainWindow.webContents.openDevTools();
}

/**
 * Start (or adopt) exactly one backend for the endpoint chosen before the
 * window was created. Never spawns a second process.
 */
async function prepareBackend(endpoint) {
  if (endpoint.port === null) {
    dialog.showErrorBox(
      'No free port for the local engine',
      `Ports ${DEFAULT_PORT}-${DEFAULT_PORT + 20} are all in use. Close the ` +
      `application holding them, or set SOVEREIGN_API_PORT to a free port and ` +
      `start SovereignAI again.\n\nNo process was terminated.`
    );
    return false;
  }

  if (endpoint.reuse) {
    console.log(`Reusing the backend already running on ${apiBaseFor(endpoint.port)}`);
    return true;
  }
  if (endpoint.moved) {
    console.log(`Port ${DEFAULT_PORT} is in use by another application; using ${endpoint.port}`);
  }

  if (readGeneralFlag('auto_start_backend', true) === false) {
    console.log('auto_start_backend=false — skipping backend spawn');
    return false;
  }

  try {
    return (await startBackend()) === true;
  } catch (err) {
    console.error('Backend start failed:', err.message);
    return false;
  }
}

async function bootBackendAndUi(endpoint) {
  const healthy = await prepareBackend(endpoint);

  // Load the UI either way: it retries /status and reconnects metricsWs, so a
  // late backend self-heals instead of leaving a dead window.
  await loadFrontend();

  if (!healthy) {
    const logHint = path.join(workspaceDir(), 'logs');
    dialog.showErrorBox(
      'Backend did not start',
      `The local engine did not answer on ${apiBaseFor(backendPort || DEFAULT_PORT)} within ` +
      `${Math.round(BACKEND_HEALTH_TIMEOUT_MS / 1000)}s.\n\n` +
      `Check for details in:\n${logHint}\n\n` +
      `Models and data live in:\n${workspaceDir()}`
    );
  }
}

// IPC Handlers
ipcMain.handle('get-app-path', () => app.getAppPath());

// The renderer's real backend address (see preload.js / additionalArguments).
ipcMain.handle('get-runtime-config', () => ({
  apiBase: apiBaseFor(backendPort || DEFAULT_PORT),
  wsUrl: wsUrlFor(backendPort || DEFAULT_PORT),
  port: backendPort || DEFAULT_PORT,
  dataRoot: roots.dataRoot,
  workspaceDir: workspaceDir(),
  portable: Boolean(roots.portableRoot),
}));

ipcMain.handle('show-notification', (event, { title, body }) => {
  if (Notification.isSupported()) {
    // ponytail: native Electron notification, no library needed
    const n = new Notification({ title, body });
    n.onclick = () => {
      if (mainWindow) {
        mainWindow.show();
        mainWindow.focus();
      }
    };
  }
  return { success: true };
});

ipcMain.handle('get-version', () => app.getVersion());

ipcMain.handle('show-open-dialog', async (event, options) => {
  return dialog.showOpenDialog(mainWindow, options);
});

ipcMain.handle('show-save-dialog', async (event, options) => {
  return dialog.showSaveDialog(mainWindow, options);
});

ipcMain.handle('restart-backend', async () => {
  await stopBackend();
  const endpoint = await resolveEndpoint(roots.dataRoot, { env: { ...process.env, SOVEREIGN_API_PORT: backendPort } });
  // A different port would need a new BrowserWindow: the renderer's address is
  // fixed in additionalArguments at window creation.
  const samePort = endpoint.port === backendPort;
  backendPort = endpoint.port || backendPort;
  if (!samePort) {
    console.warn(`Backend restarted on a different port (${backendPort}); reload the window to use it.`);
  }
  const ok = endpoint.reuse || (await startBackend()) === true;
  return { success: ok === true, port: backendPort, portChanged: !samePort };
});

protocol.registerSchemesAsPrivileged([
  { scheme: 'app', privileges: { standard: true, secure: true, supportFetchAPI: true, bypassCSP: true } }
]);

// Exactly one app instance: a second launch focuses the first window instead of
// starting a second backend against the same database.
if (!app.requestSingleInstanceLock()) {
  console.log('Another SovereignAI instance is already running — exiting this one.');
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

// App lifecycle
app.whenReady().then(async () => {
  try {
    console.log('Starting SovereignAI...');
    console.log(`Data root: ${roots.dataRoot}${roots.portableRoot ? ' (portable)' : ''}`);

    // Custom protocol for the Next.js static export
    protocol.handle('app', (request) => {
      const decodedPath = decodeURI(new URL(request.url).pathname);
      const basePath = frontendDir();
      let filePath = path.join(basePath, decodedPath);

      try {
        if (decodedPath === '/' || decodedPath === '') {
          filePath = path.join(basePath, 'index.html');
        } else if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
          const indexPath = path.join(filePath, 'index.html');
          if (fs.existsSync(indexPath)) filePath = indexPath;
        } else if (!fs.existsSync(filePath)) {
          if (fs.existsSync(path.join(filePath, 'index.html'))) {
            filePath = path.join(filePath, 'index.html');
          } else if (fs.existsSync(filePath + '.html')) {
            filePath = filePath + '.html';
          } else {
            filePath = path.join(basePath, 'index.html');
          }
        }
      } catch (err) {
        filePath = path.join(basePath, 'index.html');
      }

      const { pathToFileURL } = require('url');
      return net.fetch(pathToFileURL(filePath).href);
    });

    // Port resolution first: the window needs it, and it decides whether a
    // backend is spawned at all.
    const endpoint = await resolveEndpoint(roots.dataRoot);
    backendPort = endpoint.port;

    createWindow();
    createMenu(mainWindow, { modelsDir: path.join(workspaceDir(), 'models') });
    // The tray is optional chrome — never let it abort startup.
    tray = createTray(mainWindow);

    bootBackendAndUi(endpoint).catch((err) => {
      console.error('Backend/UI boot failed:', err);
      dialog.showErrorBox('Startup Error', `Failed to start backend: ${err.message}`);
    });

    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
        loadFrontend().catch((err) => console.error('Could not reload the UI:', err));
      } else {
        mainWindow.show();
      }
    });
  } catch (error) {
    console.error('Failed to start application:', error);
    dialog.showErrorBox('Startup Error', `Failed to start: ${error.message}`);
    app.quit();
  }
});

// One quit path for `before-quit` and `window-all-closed`: the backend is
// asked to stop and awaited, so it can close its databases first.
function quitApp(event) {
  app.isQuitting = true;
  if (quitting) return;
  quitting = true;
  if (event) event.preventDefault();
  stopBackend()
    .catch((err) => console.error('Error while stopping the backend:', err))
    .finally(() => app.quit());
}

app.on('before-quit', (event) => quitApp(event));

// Subscribing to this event is also what disables Electron's automatic quit,
// which gives stopBackend() the time it needs to close the databases.
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') quitApp();
});

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
  console.error('Uncaught Exception:', error);
  dialog.showErrorBox('Error', error.message);
});
