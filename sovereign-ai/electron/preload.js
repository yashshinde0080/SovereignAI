const { contextBridge } = require('electron')

// Simple preload script
contextBridge.exposeInMainWorld('electronAPI', {
    ping: () => 'pong'
})
