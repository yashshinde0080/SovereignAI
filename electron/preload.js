const { contextBridge, ipcRenderer } = require('electron');

// The backend port is decided at startup (it can fall back to a free one), so
// it is passed in through webPreferences.additionalArguments rather than baked
// into the frontend build. lib/apiBase.ts reads this object.
const arg = process.argv.find((a) => a.startsWith('--sovereign-api-base='));
const apiBase = arg ? arg.slice('--sovereign-api-base='.length) : null;
const wsUrl = apiBase ? `${apiBase.replace(/^http/, 'ws')}/ws/metrics` : null;

contextBridge.exposeInMainWorld('sovereignRuntime', { apiBase, wsUrl });

contextBridge.exposeInMainWorld('electronAPI', {
  // App info
  getAppPath: () => ipcRenderer.invoke('get-app-path'),
  getVersion: () => ipcRenderer.invoke('get-version'),

  // Backend address + data locations (authoritative, works even if the port
  // moved after startup)
  getRuntimeConfig: () => ipcRenderer.invoke('get-runtime-config'),

  // Dialogs
  showOpenDialog: (options) => ipcRenderer.invoke('show-open-dialog', options),
  showSaveDialog: (options) => ipcRenderer.invoke('show-save-dialog', options),
  
  // Notifications
  showNotification: (options) => ipcRenderer.invoke('show-notification', options),

  // Backend control
  restartBackend: () => ipcRenderer.invoke('restart-backend'),
  
  // Window controls
  minimize: () => ipcRenderer.send('window-minimize'),
  maximize: () => ipcRenderer.send('window-maximize'),
  close: () => ipcRenderer.send('window-close'),
  
  // Events
  onBackendStatus: (callback) => {
    ipcRenderer.on('backend-status', (event, status) => callback(status));
  },
  
  // Platform info
  platform: process.platform,
});
