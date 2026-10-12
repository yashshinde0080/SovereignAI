const { app, BrowserWindow, ipcMain, dialog, protocol, net, Notification } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const { createMenu } = require('./menu');
const { createTray } = require('./tray');

let mainWindow;
let backendProcess;
let backendStarting = false;
let tray;

const BACKEND_PORT = 8000;
const FRONTEND_PORT = 3000;
const BACKEND_HEALTH_TIMEOUT_MS = 120000;

const isDev = !app.isPackaged;

// Portable mode: run entirely off the drive the exe lives on -- no %APPDATA%,
// no host %TEMP%. Auto-on for the NSIS portable target (PORTABLE_EXECUTABLE_DIR)
// or the shipped zip layout (a sibling data/ dir next to the exe). An installed
// app (Program Files, no data/ sibling) keeps the per-user dirs.
const exeDir = isDev ? null : path.dirname(app.getPath('exe'));
const portableRoot = !isDev && (process.env.PORTABLE_EXECUTABLE_DIR
  || fs.existsSync(path.join(exeDir, 'data'))
  || process.env.SOVEREIGN_PORTABLE === '1')
  ? (process.env.PORTABLE_EXECUTABLE_DIR || exeDir)
  : null;

// Must run before anything reads a path. Portable pins Electron's userData
// (cache, session, crashpad) next to the exe; installed keeps %APPDATA%.
app.setPath('userData', portableRoot
  ? path.join(portableRoot, 'data', 'electron')
  : path.join(app.getPath('appData'), 'SovereignAI'));
if (portableRoot) app.setPath('temp', path.join(portableRoot, 'data', 'cache', 'temp'));

// Writable state lives in the data ROOT the backend appends "workspace" to
// (SOVEREIGN_DATA_ROOT -> <root>\workspace). Dev uses the repo; portable uses
// <exeDir>\data; installed uses the per-user dir.
function dataRoot() {
  if (isDev) return path.join(__dirname, '..');
  return portableRoot ? path.join(portableRoot, 'data') : app.getPath('userData');
}

function workspaceDir() {
  return path.join(dataRoot(), 'workspace');
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

function pingHealth() {
  return net.fetch(`http://127.0.0.1:${BACKEND_PORT}/health`)
    .then((res) => res.ok)
    .catch(() => false);
}

// Wait for /health to answer, not for a stdout string: line-buffering differs
// between a console python and a frozen exe.
async function waitForBackend(timeoutMs = BACKEND_HEALTH_TIMEOUT_MS) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await pingHealth()) return true;
    if (!backendProcess) return false; // died during startup
    await new Promise((r) => setTimeout(r, 500));
  }
  return false;
}

async function startBackend() {
  if (backendProcess || backendStarting) return; // never spawn twice
  backendStarting = true;

  try {
    const { cmd, args } = resolveBackendCommand();
    const dir = backendDir();
    const fullArgs = [...args, '--host', '127.0.0.1', '--port', String(BACKEND_PORT)];

    console.log('Starting backend:', cmd, fullArgs.join(' '));
    // Portable: redirect every temp/cache/config path (and HF_HOME) onto the
    // drive so nothing leaks to the host. Directories must exist up front.
    let portableEnv = {};
    if (portableRoot) {
      const data = path.join(portableRoot, 'data');
      const cache = path.join(data, 'cache');
      portableEnv = {
        TEMP: path.join(cache, 'temp'), TMP: path.join(cache, 'temp'),
        HF_HOME: path.join(cache, 'hf'),
        XDG_CACHE_HOME: cache,
        XDG_CONFIG_HOME: path.join(data, 'config'),
        XDG_DATA_HOME: path.join(data, 'share'),
      };
      for (const d of [portableEnv.TEMP, portableEnv.HF_HOME, portableEnv.XDG_CONFIG_HOME, portableEnv.XDG_DATA_HOME]) {
        try { fs.mkdirSync(d, { recursive: true }); } catch (e) { console.warn('mkdir', d, e.message); }
      }
    }
    backendProcess = spawn(cmd, fullArgs, {
      cwd: dir,
      windowsHide: true,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1',
        PYTHONDONTWRITEBYTECODE: '1',
        SOVEREIGN_DATA_ROOT: dataRoot(),
        ...portableEnv,
      },
    });
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
  });

  const ok = await waitForBackend();
  backendStarting = false;
  return ok;
}

function stopBackend() {
  const proc = backendProcess;
  if (!proc) return;
  backendProcess = null;
  console.log('Stopping backend...');
  try {
    if (process.platform === 'win32') {
      // /T kills the tree, /pid scopes it to the child we spawned — unrelated
      // python/node processes on the machine are never touched.
      spawn('taskkill', ['/pid', String(proc.pid), '/T', '/F'], { windowsHide: true });
    } else {
      proc.kill('SIGTERM');
      setTimeout(() => { try { proc.kill('SIGKILL'); } catch (_) {} }, 5000);
    }
  } catch (err) {
    console.warn('Could not stop backend:', err.message);
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

async function bootBackendAndUi() {
  const autoStart = readGeneralFlag('auto_start_backend', true) !== false;
  if (!autoStart) {
    console.log('auto_start_backend=false — skipping backend spawn');
    await loadFrontend();
    return;
  }

  let healthy = false;
  try {
    healthy = (await startBackend()) === true;
  } catch (err) {
    healthy = false;
  }

  if (!healthy) {
    if (await pingHealth()) healthy = true; // already running elsewhere
  }

  // Load the UI either way: it retries /status and reconnects metricsWs, so a
  // late backend self-heals instead of leaving a dead window.
  await loadFrontend();

  if (!healthy) {
    const logHint = path.join(workspaceDir(), 'logs');
    dialog.showErrorBox(
      'Backend did not start',
      `The local engine did not answer on port ${BACKEND_PORT} within ` +
      `${Math.round(BACKEND_HEALTH_TIMEOUT_MS / 1000)}s.\n\n` +
      `Check for details in:\n${logHint}\n\n` +
      `Models and data live in:\n${workspaceDir()}`
    );
  }
}

// IPC Handlers
ipcMain.handle('get-app-path', () => app.getAppPath());

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
  stopBackend();
  await new Promise((r) => setTimeout(r, 1000));
  const ok = await startBackend();
  return { success: ok === true };
});

protocol.registerSchemesAsPrivileged([
  { scheme: 'app', privileges: { standard: true, secure: true, supportFetchAPI: true, bypassCSP: true } }
]);

// App lifecycle
app.whenReady().then(async () => {
  try {
    console.log('Starting SovereignAI...');

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

    createWindow();
    createMenu(mainWindow);
    tray = createTray(mainWindow);

    bootBackendAndUi().catch((err) => {
      console.error('Backend/UI boot failed:', err);
      dialog.showErrorBox('Startup Error', `Failed to start backend: ${err.message}`);
    });

    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
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

app.on('before-quit', () => {
  app.isQuitting = true;
  stopBackend();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    stopBackend();
    app.quit();
  }
});

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
  console.error('Uncaught Exception:', error);
  dialog.showErrorBox('Error', error.message);
});
