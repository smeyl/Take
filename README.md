# Take

Take is a remote recording session tool that lets an engineer and an artist work together from different locations. The engineer records in Pro Tools and controls the artist's cue mix from a desktop app; the artist monitors session state and meters in a native macOS app. Recording is captured losslessly on the artist's machine, and each take is transferred back and swapped into the engineer's Pro Tools session in place of the live-streamed recording.

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
├── engineer-app/  Desktop UI the engineer runs (Electron + React + Vite)
├── backend/       Python services for BOTH sides (transport, relay, file transfer, DAW integration)
├── recordings/    Artist's local lossless takes (written by backend, git-ignored)
├── incoming/      Files the engineer receives from the artist (git-ignored)
├── docs/          Product spec and design docs
├── PORTS.md       Full port map for the running services
└── README.md
```

A session uses all three apps together: the artist runs `artist-app` + the
artist half of `backend`; the engineer runs `engineer-app` + the engineer half
of `backend`. The two halves of `backend` share modules (file transfer,
timecode), which is why they live in one Python folder.

Everything DAW-specific sits behind `backend/daw.py`. The active implementation
is `backend/pro_tools.py`, which drives Pro Tools through **PTSL** (the Pro
Tools Scripting Library, a gRPC service Pro Tools runs on `localhost:31416`)
using the [py-ptsl](https://github.com/iluvcapra/py-ptsl) client.

## Requirements

**Both machines**
- macOS
- [Homebrew](https://brew.sh) — `setup.sh` will tell you if it's missing and give you the exact install command
- Python 3.9–3.12 at `/usr/bin/python3` (**Python 3.13+ is not supported** — `pedalboard` requires ≤ 3.12)

**Engineer only**
- **Pro Tools 2025.6 or later** — Take uses PTSL commands added in 2025.6 (tested with Pro Tools 2026.4.1). PTSL runs automatically while Pro Tools is open; there is nothing to enable.
- **py-ptsl 601.1.0** — the newest py-ptsl release that supports Python 3.9 (later releases need Python ≥ 3.12)
- Node.js 18+
- A Pro Tools **Playback Engine with audio inputs** (Setup ▸ Playback Engine) that **includes Pro Tools Audio Bridge 2-A** — see [Live stream into Pro Tools](#live-stream-into-pro-tools). Pro Tools won't record-enable a track that has no input and output assigned.

`setup.sh` installs portaudio (via Homebrew) and the Python dependencies, including py-ptsl. It installs the legacy Reaper script only if Reaper is installed. If Homebrew itself is missing, it will tell you and stop — install Homebrew first, then re-run `./setup.sh`.

## Setup

### 1. Clone the repo (both machines)

```bash
git clone https://github.com/smeyl/Take
cd Take
```

### 2. If you are the engineer

```bash
cd backend
./setup.sh           # Python dependencies, including py-ptsl

cd ../engineer-app
npm install          # desktop app dependencies
```

### 3. If you are the artist

```bash
cd backend
./setup.sh          # installs Python dependencies
```

That's it — the artist app (Take Artist.app) is already built and ready to run. No Node.js, Xcode or Pro Tools needed on the artist's machine.

## Running a session

### If you are the engineer

1. Open Pro Tools and open (or create) your session
2. Arm the track you want to record the artist on
3. Double-click **Take Engineer.app** — a session code appears; share it with the artist
4. Press **Record** in Pro Tools when ready. Take follows Pro Tools' transport: the artist gets a 3-2-1 countdown and records losslessly on their machine
5. Press **Stop** in Pro Tools. The artist's take is transferred back automatically and **swapped in** on the armed track, replacing the live-streamed recording, at the position where the artist's recording actually began

The engineer app shows which track is armed next to the Pro Tools connection row, and lists takes as they arrive. With **Auto-sync takes** off (Settings), takes wait in the list until you press **Sync now**.

### If you are the artist

1. Double-click **Take Artist.app**
2. Enter the session code the engineer shared with you
3. Put on headphones — you will hear yourself through the cue mix
4. Perform when the engineer starts recording

Take records one input — the one your mic is on — from the Mac's default input device. To use an audio interface, set `TAKE_INPUT_DEVICE` to its name (or part of it); if your mic isn't on input 1, set `TAKE_INPUT_CHANNEL` to its input number (e.g. `2`). Only that input is recorded, streamed and metered: other inputs on the interface are never mixed in.

### What Take does in your Pro Tools session

Take only acts when a take arrives, and only on the track that was armed:

- it clears the full extent of the live-streamed recording of that take and places the lossless file at the position the artist's capture began (imported via the clip list, converted to the session's sample rate if needed)
- if the session is in **Shuffle** edit mode, Take switches to Slip for that edit and restores Shuffle afterwards, so later clips never move
- it checks the edit selection matches before clearing anything; with *Link Timeline and Edit Selection* turned off it won't clear, and places the take on top of the streamed recording instead
- it never changes track inputs, routing, or arm state

### Known limitations with Pro Tools

- **No playhead read in PTSL.** Take works out positions from where the transport started plus elapsed time. Takes are placed by where the artist was in their backing track when capture began, so this only affects placement when no backing track is playing (it then lands late by the network round trip and audio latencies). The timecode that keeps the artist's backing track in sync doesn't follow loops, pre-roll, scrubbing, or seeking while the transport is rolling. Pro Tools also reports that it has started only to within about ±15–20 ms of when its audio actually starts (measured), so what you hear lines up to within that, varying from one playback start to the next. Takes are unaffected: they're placed sample-accurately regardless.
- **Take doesn't start Pro Tools recording itself** — the engineer presses Record in Pro Tools.
- **Not yet tested:** pre-roll, loop record, QuickPunch, Shuffle mode, *Link Timeline and Edit Selection* turned off.
- **Backing track bounce:** the backend can export the session's mix from Pro Tools as MP3 and send it to the artist (the bounce service on port 5006), but the current engineer app has no button for it.

### Live stream into Pro Tools

While the artist performs, the engineer backend plays their live mic stream into a virtual audio device so Pro Tools can monitor and record it on the armed track (the lossless take replaces that recording afterwards). By default that device is **Pro Tools Audio Bridge 2-A**; set `TAKE_STREAM_DEVICE` to use another one. The stream is held in a fixed 40 ms buffer against network jitter before it's played, so its delay stays constant; set `TAKE_STREAM_BUFFER_MS` to change it (more for a shaky connection, less for tighter monitoring).

So that you hear the artist in time with the session, the artist's backing track plays ahead of Pro Tools by the whole loop's delay: the network round trip, both machines' audio latencies, the stream buffer, and a fixed Pro Tools offset (`TAKE_DAW_INPUT_OFFSET_MS`, default 47 ms, mostly Pro Tools' own input-monitoring latency, which grows with its H/W buffer size). The amount is worked out when playback starts and held until it stops; the artist backend logs it. If the vocal sounds consistently early or late, adjust `TAKE_DAW_INPUT_OFFSET_MS` by that much.

The device must **not** be Pro Tools' Playback Engine device itself: Pro Tools takes that device over, and audio other apps send to it never arrives (tested with Audio Bridge 16 as the engine — Pro Tools recorded digital silence). Instead, use a Playback Engine that *includes* Audio Bridge 2-A as inputs:

1. Audio MIDI Setup ▸ **+** ▸ **Create Aggregate Device**, with **Pro Tools Audio Bridge 2-A** and your output device (e.g. your speakers or interface)
2. Pro Tools ▸ Setup ▸ **Playback Engine** → that aggregate device
3. Pro Tools ▸ Setup ▸ **I/O** ▸ Input: a path on the Audio Bridge 2-A channels, and set the recording track's input to it

Changing the Playback Engine clears record-enable, so re-arm the track afterwards. With this setup, Pro Tools records the artist's live mic on the armed track (tested with Pro Tools 2026.4.1).

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

## Legacy: Reaper

Take started with Reaper as its DAW, controlled through a Lua script (`take_session.lua`) over file-based IPC. That integration is preserved on the [`reaper`](https://github.com/smeyl/Take/tree/reaper) branch and is no longer the main path. `backend/reaper.py` and `take_session.lua` remain on `main` as a reference implementation of the same DAW interface, but `daw.py` uses Pro Tools.

## Built with

- **[JUCE](https://juce.com/)** — native macOS artist app (C++)
- **[Electron](https://www.electronjs.org/)** — engineer desktop app (with React + Vite)
- **[Python](https://www.python.org/)** — backend services for transport, relay, file transfer, and timecode
- **[Pro Tools](https://www.avid.com/pro-tools)** + **[PTSL](https://developer.avid.com/)** via **[py-ptsl](https://github.com/iluvcapra/py-ptsl)** — the engineer's DAW (transport, arm state, take swap, bounce)

## License

Released under the [MIT License](LICENSE). Copyright (c) 2026 Arda Akıncı.
