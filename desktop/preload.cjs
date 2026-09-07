const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('electron', {
  openLiveAssist: () => ipcRenderer.send('fireflies:open-live-assist'),
  getDesktopSource: () => ipcRenderer.invoke('fireflies:get-desktop-source'),
  closeLiveAssist: () => ipcRenderer.send('fireflies:close-live-assist')
});
