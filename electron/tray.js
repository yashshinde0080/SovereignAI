const { Tray, Menu, nativeImage, app } = require('electron');
const path = require('path');

function createTray(mainWindow) {
  // assets/icon.png ships in the package (tray-icon.png never did, so the tray
  // got an empty image and either threw — which aborted the whole startup — or
  // produced an invisible icon the user could only force-quit).
  const iconPath = path.join(__dirname, 'assets', 'icon.png');

  // The tray is optional chrome: a missing/undecodable icon must not stop the app.
  let tray;
  try {
    let trayIcon = nativeImage.createFromPath(iconPath);
    if (trayIcon.isEmpty()) throw new Error(`empty tray icon: ${iconPath}`);
    if (process.platform === 'darwin') {
      trayIcon = trayIcon.resize({ width: 16, height: 16 });
    }
    tray = new Tray(trayIcon);
  } catch (error) {
    console.error('Tray unavailable:', error.message);
    return null;
  }

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Show SovereignAI',
      click: () => {
        mainWindow.show();
      }
    },
    {
      label: 'Hide',
      click: () => {
        mainWindow.hide();
      }
    },
    { type: 'separator' },
    {
      label: 'Open Chat',
      click: () => {
        mainWindow.show();
        mainWindow.webContents.send('navigate', '/chat');
      }
    },
    {
      label: 'System Info',
      click: () => {
        mainWindow.show();
        mainWindow.webContents.send('navigate', '/system');
      }
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => {
        app.isQuitting = true;
        app.quit();
      }
    }
  ]);

  tray.setToolTip('SovereignAI Edge');
  tray.setContextMenu(contextMenu);

  tray.on('click', () => {
    if (mainWindow.isVisible()) {
      mainWindow.hide();
    } else {
      mainWindow.show();
    }
  });

  tray.on('double-click', () => {
    mainWindow.show();
  });

  return tray;
}

module.exports = { createTray };