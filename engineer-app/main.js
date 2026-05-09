const { app, BrowserWindow } = require('electron')
const path = require('path')

function createWindow() {
  const win = new BrowserWindow({
    width: 820,
    height: 700,
    backgroundColor: '#0a0a0b',
    titleBarStyle: 'hiddenInset',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    }
  })

  if (process.env.NODE_ENV === 'development') {
    // Wait for Vite to be ready before loading
    setTimeout(() => {
      win.loadURL('http://localhost:5173')
    }, 2000)
  } else {
    win.loadFile(path.join(__dirname, 'dist/index.html'))
  }
}

app.whenReady().then(createWindow)
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit() })
