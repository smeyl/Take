# Take

Remote recording session tool for engineers and artists. The engineer controls transport and cue mix from a web app; the artist sees session state and meters in a native macOS app.

## Requirements

- macOS with Python 3.9 at `/usr/bin/python3` (standard on older Macs), or install Python 3.11 and adjust the scripts
- **Python 3.13+ is not supported** — `pedalboard` requires Python ≤ 3.12
- Node.js 18+
- Reaper (with web interface enabled)

## Setup

### 1. Clone the repo

```bash
git clone <repo-url>
cd Take
```

### 2. Companion app (Python backend)

```bash
cd companion-app
./setup.sh
```

This installs all dependencies directly to `/usr/bin/python3`.

### 3. Engineer web app

```bash
cd engineer-app
npm install
```

## Running

### Engineer (web app + Python backend)

```bash
# Terminal 1 — Python services
cd companion-app
./dev_engineer.sh

# Terminal 2 — React dev server
cd engineer-app
npm run start
```

Open `http://localhost:3000` in your browser.

### Artist (native macOS app + Python backend)

```bash
cd companion-app
./dev_artist.sh
```

Or to launch the compiled app bundle alongside the backend:

```bash
cd companion-app
./start_take_artist.sh
```

## Reaper setup

1. Enable the web interface: **Preferences → Control/OSC/web → Add → Web browser interface** (port 8080)
2. Install the export script: copy `companion-app/take_export_markers.lua` to `~/Library/Application Support/REAPER/Scripts/`
3. When you open a new project, run the script via **Actions → Run ReaScript → take_export_markers.lua** to export markers. Re-run it whenever markers change.
