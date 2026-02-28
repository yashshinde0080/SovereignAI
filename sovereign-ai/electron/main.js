const { app, BrowserWindow } = require("electron")
const { spawn } = require("child_process")
const path = require("path")

let backendProcess

function startBackend() {
  const isDev = !app.isPackaged
  const backendPath = isDev
    ? path.join(__dirname, '..', 'backend', 'main.py')
    : path.join(process.resourcesPath, 'backend', 'main.py') // Real implementation would use backend.exe if packed

  // In a real scenario we use python from the virtual env or system path
  backendProcess = spawn("python", [backendPath])

  backendProcess.stdout.on('data', (data) => {
    console.log(`Backend stdout: ${data}`);
  });

  backendProcess.stderr.on('data', (data) => {
    console.error(`Backend stderr: ${data}`);
  });
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1400,
    height: 900,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false
    }
  })

  // We load Next.js in dev mode for this demo
  // For production, Next.js static files would be loaded
  win.loadURL("http://localhost:3000")
}

app.whenReady().then(() => {
  // startBackend()  // Disabled for demo since we'd run backend and frontend separately for dev
  createWindow()

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit()
})

app.on("quit", () => {
  if (backendProcess) {
    backendProcess.kill()
  }
})
