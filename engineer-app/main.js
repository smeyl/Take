const { app, BrowserWindow, ipcMain } = require('electron')
const path = require('path')

const DEV = process.env.NODE_ENV === 'development'

let mainWin = null
let cueWin = null
let lastCue = null  // latest cue values, handed to the popout when it opens

function loadRenderer(win, hash) {
  if (DEV) {
    win.loadURL(`http://localhost:5173/${hash ? '#' + hash : ''}`)
  } else {
    win.loadFile(path.join(__dirname, 'dist/index.html'), hash ? { hash } : undefined)
  }
}

const webPreferences = {
  nodeIntegration: false,
  contextIsolation: true,
  preload: path.join(__dirname, 'preload.js'),
}

function createWindow() {
  mainWin = new BrowserWindow({
    width: 500,
    height: 420,
    backgroundColor: '#0a0a0b',
    titleBarStyle: 'hiddenInset',
    trafficLightPosition: { x: 12, y: 12 },
    webPreferences,
  })

  // The popout is a satellite of the session window — never leave it orphaned.
  mainWin.on('closed', () => {
    mainWin = null
    if (cueWin) cueWin.close()
  })

  if (DEV) {
    // Wait for Vite to be ready before loading
    setTimeout(() => loadRenderer(mainWin), 2000)
  } else {
    loadRenderer(mainWin)
  }
}

function openCuePopout() {
  if (cueWin) { cueWin.focus(); return }
  cueWin = new BrowserWindow({
    width: 300,
    height: 300,
    resizable: false,
    fullscreenable: false,
    alwaysOnTop: true,  // pinned by default — stays above Reaper / Pro Tools
    backgroundColor: '#0a0a0b',
    titleBarStyle: 'hiddenInset',
    trafficLightPosition: { x: 10, y: 10 },
    webPreferences,
  })
  cueWin.setAlwaysOnTop(true, 'floating')
  cueWin.on('closed', () => {
    cueWin = null
    if (mainWin) mainWin.webContents.send('cue-popout:closed')
  })
  loadRenderer(cueWin, 'cue-popout')
}

ipcMain.on('cue-popout:open', (_e, cue) => {
  if (cue) lastCue = cue
  openCuePopout()
})

ipcMain.on('cue-popout:close', () => { if (cueWin) cueWin.close() })

ipcMain.on('cue-popout:set-pinned', (_e, pinned) => {
  if (cueWin) cueWin.setAlwaysOnTop(Boolean(pinned), 'floating')
})

ipcMain.handle('cue:get', () => lastCue)

// Forward knob changes from one window to the other so both stay in sync.
ipcMain.on('cue:changed', (e, cue) => {
  lastCue = cue
  for (const win of [mainWin, cueWin]) {
    if (win && win.webContents !== e.sender) win.webContents.send('cue:changed', cue)
  }
})

app.whenReady().then(createWindow)
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit() })
