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

`npm run start` launches the Vite dev server and the Electron shell together. (To use a browser instead, open `http://localhost:5173`.)

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

### Two machines

The relay (port 5010) runs on the engineer's machine. The artist's backend finds it via the session file written by the Take app, or you can point it there explicitly:

```bash
TAKE_RELAY_HOST=<engineer-ip> ./dev_artist.sh
```

Both machines must be reachable on ports 5001–5010 (same LAN or VPN). See [PORTS.md](PORTS.md) for the full port map; each startup script checks its ports and reports conflicts instead of failing silently.

## Reaper setup

1. Enable the web interface: **Preferences → Control/OSC/web → Add → Web browser interface** (port 8080)
2. Run `companion-app/setup.sh` — it installs `take_session.lua` plus an auto-start hook (`Scripts/__startup.lua`). Every Reaper launch then automatically:
   - listens for Take's transport commands (record/stop/RTZ/swap)
   - keeps track and marker exports current — no manual script runs needed
   - self-registers the insert action — no command-ID copying needed

After that, a session is: open Reaper, double-click Take Engineer.app, and pick a destination track in the engineer app — Take arms it and sets its input to BlackHole automatically.
