const { app, BrowserWindow, shell, ipcMain, desktopCapturer, session } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const http = require('http');

const APP_ID = 'com.firefliesclone.desktop';
const APP_VERSION = '2.4.0';
app.setAppUserModelId(APP_ID);
ipcMain.handle('fireflies:get-desktop-source', async () => {
  const sources = await desktopCapturer.getSources({ types: ['screen'], thumbnailSize: { width: 1, height: 1 }, fetchWindowIcons: false });
  return sources[0] ? { id: sources[0].id, name: sources[0].name } : null;
});

let win = null;
let liveWin = null;
let backend = null;
const isPackaged = app.isPackaged;
const projectRoot = path.join(__dirname, '..');
const resourceRoot = isPackaged ? process.resourcesPath : projectRoot;
const frontendOut = path.join(app.getAppPath(), 'frontend', 'out');
const backendExe = path.join(resourceRoot, 'backend', 'fireflies-backend.exe');
const backendDir = path.dirname(backendExe);
const PORT = 8000;
let FRONTEND_PORT = 3210;
let frontendServer = null;

function startBackend() {
  const dbPath = path.join(app.getPath('userData'), 'data', 'fireflies.db');
  fs.mkdirSync(path.dirname(dbPath), { recursive: true });

  if (isPackaged) {
    if (!fs.existsSync(backendExe)) throw new Error(`Backend executable missing: ${backendExe}`);
    backend = spawn(backendExe, [], {
      cwd: backendDir,
      windowsHide: true,
      env: { ...process.env, FIREFLIES_HOST: '127.0.0.1', FIREFLIES_PORT: String(PORT), FIREFLIES_DB_PATH: dbPath }
    });
  } else {
    const py = process.platform === 'win32' ? 'py' : 'python3';
    const args = process.platform === 'win32'
      ? ['-3.11', '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)]
      : ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)];
    backend = spawn(py, args, {
      cwd: path.join(projectRoot, 'backend'),
      windowsHide: true,
      shell: false,
      env: { ...process.env, FIREFLIES_DB_PATH: dbPath }
    });
  }
  backend.on('error', (err) => console.error('[backend]', err));
  backend.stderr?.on('data', d => console.log('[backend]', d.toString()));
}

function waitForBackend(timeoutMs = 15000) {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const probe = () => {
      const req = http.get(`http://127.0.0.1:${PORT}/api/health`, res => {
        if (res.statusCode === 200) return resolve();
        res.resume();
        retry();
      });
      req.on('error', retry);
      req.setTimeout(1000, () => { req.destroy(); retry(); });
    };
    const retry = () => {
      if (Date.now() - started > timeoutMs) return reject(new Error('Fireflies Clone backend did not start in time.'));
      setTimeout(probe, 200);
    };
    probe();
  });
}

function startFrontendServer() {
  if (!isPackaged) return Promise.resolve();
  if (!fs.existsSync(path.join(frontendOut, 'index.html'))) {
    throw new Error(`Frontend build missing: ${path.join(frontendOut, 'index.html')}`);
  }
  const mime = {
    '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.svg': 'image/svg+xml',
    '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp',
    '.ico': 'image/x-icon', '.woff': 'font/woff', '.woff2': 'font/woff2', '.map': 'application/json'
  };
  return new Promise((resolve, reject) => {
    frontendServer = http.createServer((req, res) => {
      try {
        const raw = decodeURIComponent((req.url || '/').split('?')[0]);
        const relative = raw === '/' ? 'index.html' : raw.replace(/^\/+/, '');
        const root = path.resolve(frontendOut);
        let file = path.resolve(root, relative);
        if (!file.startsWith(root + path.sep) && file !== root) { res.writeHead(403); return res.end('Forbidden'); }
        if (!fs.existsSync(file) || fs.statSync(file).isDirectory()) file = path.join(root, 'index.html');
        const ext = path.extname(file).toLowerCase();
        res.setHeader('Content-Type', mime[ext] || 'application/octet-stream');
        res.setHeader('Cache-Control', ext === '.html' ? 'no-cache' : 'public, max-age=31536000');
        fs.createReadStream(file).pipe(res);
      } catch (e) { res.writeHead(500); res.end('Internal error'); }
    });
    frontendServer.once('error', (err) => {
      if (err.code === 'EADDRINUSE' && FRONTEND_PORT !== 0) {
        frontendServer.removeAllListeners('error');
        FRONTEND_PORT = 0;
        frontendServer.listen(0, '127.0.0.1');
        return;
      }
      reject(err);
    });
    frontendServer.listen(FRONTEND_PORT, '127.0.0.1', () => {
      const address = frontendServer.address();
      if (address && typeof address === 'object') FRONTEND_PORT = address.port;
      resolve();
    });
  });
}

function createWindow() {
  win = new BrowserWindow({
    width: 1500, height: 920, minWidth: 1050, minHeight: 700,
    backgroundColor: '#090a0d', title: 'Fireflies Clone', autoHideMenuBar: true, show: false,
    webPreferences: { contextIsolation: true, nodeIntegration: false, preload: path.join(__dirname, 'preload.cjs') }
  });
  win.once('ready-to-show', () => win.show());
  win.webContents.setWindowOpenHandler(({ url }) => { shell.openExternal(url); return { action: 'deny' }; });
  if (isPackaged) win.loadURL(`http://127.0.0.1:${FRONTEND_PORT}/`);
  else win.loadURL('http://localhost:3000');
  win.webContents.on('did-fail-load', (_event, errorCode, errorDescription) => {
    console.error('[renderer]', errorCode, errorDescription);
  });
}

function createLiveAssistWindow() {
  if (liveWin && !liveWin.isDestroyed()) { liveWin.focus(); return; }
  liveWin = new BrowserWindow({
    width: 1540, height: 940, minWidth: 1050, minHeight: 700,
    backgroundColor: '#090a0d', title: 'Live Assist', autoHideMenuBar: true,
    webPreferences: { contextIsolation: true, nodeIntegration: false, preload: path.join(__dirname, 'preload.cjs') }
  });
  liveWin.on('closed', () => { liveWin = null; });
  const url = isPackaged ? `http://127.0.0.1:${FRONTEND_PORT}/#live-assist` : 'http://localhost:3000/#live-assist';
  liveWin.loadURL(url);
}

ipcMain.on('fireflies:open-live-assist', () => createLiveAssistWindow());
ipcMain.on('fireflies:close-live-assist', () => { if (liveWin && !liveWin.isDestroyed()) liveWin.close(); });

app.whenReady().then(async () => {
  // Electron's defaultSession is only available after app is ready.
  // Register permission handlers here (not at module load time) so the
  // packaged Windows build cannot crash with:
  // `Session can only be received when app is ready`.
  const defaultSession = session.defaultSession;
  defaultSession.setPermissionRequestHandler((_webContents, permission, callback) => {
    callback(
      permission === 'media' ||
      permission === 'clipboard-read' ||
      permission === 'clipboard-sanitized-write'
    );
  });
  if (typeof defaultSession.setPermissionCheckHandler === 'function') {
    defaultSession.setPermissionCheckHandler((_webContents, permission) => {
      return (
        permission === 'media' ||
        permission === 'clipboard-read' ||
        permission === 'clipboard-sanitized-write'
      );
    });
  }

  try {
    startBackend();
    await waitForBackend();
    await startFrontendServer();
    createWindow();
  } catch (err) {
    console.error(err);
    const { dialog } = require('electron');
    dialog.showErrorBox('Fireflies Clone', String(err.message || err));
    app.quit();
  }
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (backend) backend.kill();
  if (liveWin && !liveWin.isDestroyed()) liveWin.close();
  if (frontendServer) frontendServer.close();
  if (process.platform !== 'darwin') app.quit();
});
app.on('before-quit', () => { if (backend) backend.kill(); if (liveWin && !liveWin.isDestroyed()) liveWin.close(); if (frontendServer) frontendServer.close(); });
