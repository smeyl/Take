# Take

Take is a remote recording session tool that lets an engineer and an artist work together from different locations. The engineer controls transport and cue mix from a web app, while the artist monitors session state and meters in a native macOS app. Recording is captured losslessly on the artist's machine and the takes are transferred back to the engineer, with Reaper driving the actual capture.

## Screenshots

> _Screenshots coming soon._
>
> <!-- Add images here, e.g.:
> ![Engineer web app](docs/screenshots/engineer.png)
> ![Artist macOS app](docs/screenshots/artist.png) -->

## Project layout

```
Take/
├── artist-app/    Native macOS app the artist runs (JUCE / C++, Xcode project)
├── engineer-app/  Web UI the engineer runs (Electron + React + Vite)
├── backend/       Python services for BOTH sides (transport, relay, file transfer, Reaper)
├── recordings/    Artist's local lossless takes (written by backend, git-ignored)
├── incoming/      Files the engineer receives from the artist (git-ignored)
├── docs/          Product spec and design docs
├── PORTS.md       Full port map for the running services
└── README.md
```

A session uses all three apps together: the artist runs `artist-app` + the
artist half of `backend`; the engineer runs `engineer-app` + the engineer half
of `backend`. The two halves of `backend` share modules (file transfer, Reaper
control, timecode), which is why they live in one Python folder.

## Requirements

- macOS
- [Homebrew](https://brew.sh) — `setup.sh` will tell you if it's missing and give you the exact install command
- Python 3.9–3.12 at `/usr/bin/python3` or installed separately (**Python 3.13+ is not supported** — `pedalboard` requires ≤ 3.12)
- Node.js 18+ (engineer only)
- Reaper with web interface enabled (engineer only)

`setup.sh` handles installing portaudio (via Homebrew) and all Python dependencies automatically. If Homebrew itself is missing, it will tell you and stop — install Homebrew first, then re-run `./setup.sh`.

## Setup

### 1. Clone the repo (both machines)

```bash
git clone https://github.com/smeyl/Take
cd Take
```

### 2. If you are the engineer

```bash
cd backend
./setup.sh          # installs Python dependencies

cd ../engineer-app
npm install          # installs the web app dependencies
```

### 3. If you are the artist

```bash
cd backend
./setup.sh          # installs Python dependencies
```

That's it — the artist app (Take Artist.app) is already built and ready to run. No Node.js or Xcode needed on the artist's machine.

## Running

### If you are the engineer

1. Open Reaper, set your recording track's input to BlackHole 2ch, and arm it
2. Double-click **Take Engineer.app**
3. A session code appears — share it with the artist
4. Press **Record** in Reaper when ready — the artist gets a 3-2-1 countdown and records locally; press **Stop** in Reaper to end the take

### If you are the artist

1. Double-click **Take Artist.app**
2. Enter the session code the engineer shared with you
3. Put on headphones — you will hear yourself through the cue mix
4. Perform when the engineer starts recording

### For development (manual launch)

**Engineer:**
```bash
cd backend && ./dev_engineer.sh
cd engineer-app && npm run start
```

**Artist:**
```bash
cd backend && ./dev_artist.sh
```

### Two machines

The relay (port 5010) runs on the engineer's machine. The artist's backend finds it via the session file written by the Take app, or you can point it there explicitly:

```bash
TAKE_RELAY_HOST=<engineer-ip> ./dev_artist.sh
```

Both machines must be reachable on ports 5001–5010 (same LAN or VPN). See [PORTS.md](PORTS.md) for the full port map; each startup script checks its ports and reports conflicts instead of failing silently.

## Reaper setup

Run `backend/setup.sh` — it installs `take_session.lua` plus an auto-start hook (`Scripts/__startup.lua`). Every Reaper launch then automatically:
   - listens for Take's transport commands (record/stop/RTZ/swap/insert/bounce)
   - keeps track, marker, and transport-state exports current — no manual script runs needed

All Reaper control is file-based Lua IPC; Take does not use Reaper's web control API at all.

**Bounce & send** needs no setup: each bounce renders the master mix of the entire project to a uniquely named MP3 in `/tmp` (so Reaper never shows an overwrite prompt), sends it to the artist, and restores your project's own render settings afterwards.

After that, a session is: open Reaper, double-click Take Engineer.app, and record with Reaper's own transport. Take follows it — Record in Reaper starts the artist's countdown and lossless capture, Stop ends it, and the lossless file replaces the streamed take on the track Reaper recorded. Take is minimally invasive in Reaper: it never changes track inputs, routing or arm state. Set the recording track's input (e.g. BlackHole for the live artist stream) yourself, once, as part of your project template.

## Built with

- **[JUCE](https://juce.com/)** — native macOS artist app (C++)
- **[Electron](https://www.electronjs.org/)** — engineer desktop web app (with React + Vite)
- **[Python](https://www.python.org/)** — backend services for transport, relay, file transfer, and timecode
- **[Reaper](https://www.reaper.fm/)** — DAW on the engineer's side, driven by file-based Lua IPC (transport, take swap, timeline)

## License

Released under the [MIT License](LICENSE). Copyright (c) 2026 Arda Akıncı.
