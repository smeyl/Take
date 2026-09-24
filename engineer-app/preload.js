const { contextBridge, ipcRenderer } = require('electron')

// Narrow bridge for the detached cue mix window. Cue values live in React
// state only (never read back from the backend), so the two windows keep each
// other current through the main process.
function subscribe(channel, cb) {
  const handler = (_e, payload) => cb(payload)
  ipcRenderer.on(channel, handler)
  return () => ipcRenderer.removeListener(channel, handler)
}

contextBridge.exposeInMainWorld('take', {
  openCuePopout:  (cue) => ipcRenderer.send('cue-popout:open', cue),
  closeCuePopout: () => ipcRenderer.send('cue-popout:close'),
  setCuePinned:   (pinned) => ipcRenderer.send('cue-popout:set-pinned', pinned),
  getCue:         () => ipcRenderer.invoke('cue:get'),
  cueChanged:     (cue) => ipcRenderer.send('cue:changed', cue),
  onCueChanged:      (cb) => subscribe('cue:changed', cb),
  onCuePopoutClosed: (cb) => subscribe('cue-popout:closed', cb),
})
