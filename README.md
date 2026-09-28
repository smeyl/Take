# Take

Take lets a recording engineer and an artist in different places record together. The engineer runs the session in **Pro Tools** on their Mac. The artist sings or plays on their own Mac, hears themselves and the session through a cue mix, and their performance is **recorded losslessly on their own machine**. When the engineer stops, the lossless take is sent back automatically and dropped into the engineer's Pro Tools session, in place of the live preview Pro Tools recorded while the artist performed.

Take supports **Pro Tools only**, on macOS. (It started out on Reaper; that version is kept on the [`reaper`](https://github.com/smeyl/Take/tree/reaper) branch but is no longer maintained. See [Legacy: Reaper](#legacy-reaper).)

> **Testing status.** Sessions on one local network are well tested. Internet sessions over Tailscale have been tried only by one person operating both Macs, on two different networks (a phone hotspot and a home connection), in a test run on 26–27 September 2026: recording, take transfer, the backing track and the live preview all worked, but the connection was a worst case and the live preview dropped out during congestion. A real session with two people in two locations hasn't happened yet, so treat internet sessions as experimental.

## How it works

```
 ENGINEER'S MAC                                     ARTIST'S MAC
 Pro Tools  ◄─ PTSL ─►  Take (engineer)  ◄──────►  Take (artist)  ◄─ mic / headphones
                        · session code              · records the lossless take
                        · cue mix knobs             · plays the backing track in sync
                        · receives takes            · streams the mic live (preview only)
```

- The **engineer** presses Record and Stop in Pro Tools as usual. Take follows Pro Tools' transport; it never presses Record itself.
- While Pro Tools records, the **artist's mic is streamed live** to the engineer. Pro Tools records that stream on the armed track so the engineer can hear and see the take as it happens.
- At the same time the **artist's Mac records the take losslessly**. When Pro Tools stops, that file is transferred back and swapped in on the armed track, at the exact position it belongs.
- The two Macs talk directly: on the same network, or over the internet through **[Tailscale](https://tailscale.com)**, a free private network between your devices. Nothing goes through a Take server.

## Requirements

**Both Macs**
- macOS on Apple Silicon or Intel
- [Homebrew](https://brew.sh). Take's first run tells you if it's missing, with the command to install it.
- Python 3.9–3.12 at `/usr/bin/python3`. This is Apple's Python; it comes with the Command Line Tools (`xcode-select --install`). **Python 3.13+ is not supported**: the audio effects library (`pedalboard`) needs 3.12 or earlier.
- [Tailscale](https://tailscale.com/download), if you're in different places (see [Connecting over the internet](#connecting-over-the-internet-tailscale))

**Engineer's Mac only**
- **Pro Tools 2025.6 or later** (tested with 2026.4.1). Take controls it through **PTSL**, Pro Tools' scripting interface, which runs automatically whenever Pro Tools is open. There's nothing to turn on.
- [Node.js](https://nodejs.org) 18 or later, for the engineer app
- A one-time Pro Tools audio setup, described in [Pro Tools setup](#pro-tools-setup-engineer-once)

The artist doesn't need Pro Tools, Node.js or Xcode: the artist app comes ready-built in this repository.

## Setup

### 1. Get Take (both Macs)

```bash
git clone https://github.com/smeyl/Take
```

Keep the `Take` folder wherever you like.

### 2. Open it once (both Macs)

In the `Take` folder, double-click **Take Engineer.app** (engineer) or **Take Artist.app** (artist). Each opens a Terminal window; leave it open while you use Take.

The first time, it sets Take up in that window before starting: it installs the Python packages (`backend/setup.sh`) and, for the engineer, the engineer app's packages (`npm install`). This takes a few minutes. If something is missing (Homebrew, Node.js, the Command Line Tools) it says what to install and stops; install it and open the app again. After that, it starts straight away.

macOS may ask a few things the first time. Answer them like this:
- **"…can't be opened because it is from an unidentified developer"**: Take isn't notarized. Right-click the app ▸ **Open** ▸ **Open**. You only need to do this once per app. The artist app itself lives at `artist-app/prebuilt/Take.app`; if macOS blocks that one too, do the same for it.
- **"Terminal would like to access the microphone"** (artist): **Allow**. Take records the mic from the Terminal window's backend.
- **"Do you want the application "Python" to accept incoming network connections?"**: **Allow**, on both Macs. The two Macs connect to each other directly.

## Pro Tools setup (engineer, once)

While the artist performs, Take plays their live mic into a virtual audio device, **Pro Tools Audio Bridge 2-A**, which is installed with Pro Tools. Pro Tools records it from there on the armed track. For Pro Tools to hear that device, its Playback Engine must *include* Audio Bridge 2-A as inputs, alongside the device you listen on. You do that with a macOS *aggregate device*:

1. **Create the aggregate device.** Open **Audio MIDI Setup** (in Applications ▸ Utilities). Click **+** at the bottom left ▸ **Create Aggregate Device**. In the list on the right, tick **Pro Tools Audio Bridge 2-A** first, then the device you listen on (your interface, or MacBook Pro Speakers). You can rename it, e.g. "Take".
2. **Use it in Pro Tools.** In Pro Tools: **Setup ▸ Playback Engine** ▸ choose the aggregate device ▸ OK.
3. **Check the inputs.** **Setup ▸ I/O ▸ Input**: there should be input paths for the aggregate's channels. Audio Bridge 2-A's two channels come first if you ticked it first, so they are inputs 1–2. If the list is empty, click **Default**.
4. **Set up the track.** Create (or pick) a **mono** audio track for the artist. Set its input to **aggregate input 1**, which is Audio Bridge 2-A channel 1, where Take sends the mic. Give it an output, and record-arm it. Pro Tools won't arm a track that has no input or output assigned.

Changing the Playback Engine clears record-enable, so re-arm the track afterwards.

Don't make Audio Bridge 2-A (or any Audio Bridge) the Playback Engine itself. Pro Tools takes that device over, and audio from other apps never arrives: the track records silence.

Pro Tools' **H/W buffer size** (Setup ▸ Playback Engine) adds to what you hear of the artist's timing. Take is calibrated for the setup it was tested on (see `TAKE_DAW_INPUT_OFFSET_MS` under [Settings](#settings)).

## Connecting over the internet (Tailscale)

On the same network (same Wi-Fi or office), skip this: the artist just types the session code.

> Internet sessions are **experimental**: tested only by one person running both Macs across two networks, not yet by two people in two locations. See the testing status at the top.

In different places, the two Macs connect over **Tailscale**. Tailscale builds a private, encrypted network between devices you choose. Take uses it only to reach the other Mac; nothing goes through Take or a Take server. The free plan is enough.

Each person uses **their own Tailscale account**, and each **shares their Mac with the other**. Sharing has to go both ways: a Mac someone shares with you can only *answer* your connections, never start its own, and Take needs both Macs to reach each other.

**Each person, on their own Mac:**

1. Download Tailscale from [tailscale.com/download](https://tailscale.com/download) (or the Mac App Store), install it, and open it.
2. When macOS asks to add a VPN configuration, click **Allow**. You may be asked for your Mac's password.
3. Click the Tailscale icon in the menu bar ▸ **Log in**, and sign in or create a free account in the browser (Google, Apple, Microsoft or GitHub).
4. Check that the menu-bar icon shows **Connected** and lists your Mac with an address starting with **100.**. That's your Tailscale address.

**Share your Mac with the other person (both of you):**

5. Open the Tailscale admin console's **Machines** page, [console.tailscale.com/admin/machines](https://console.tailscale.com/admin/machines), signed in as yourself.
6. Find your Mac in the list, open the **⋯** menu at the end of its row ▸ **Share**.
7. Invite the other person **by email** (enter their address), or create a **link** and send it to them yourself. Unused links expire after 30 days.
8. The other person opens the email or link, signs in to *their* Tailscale account, and clicks **Accept**.

After **both** of you have shared and accepted, each Mac appears in the other's Tailscale menu. You can check from Terminal: `ping 100.x.y.z` with the other Mac's address should get replies.

Do the sharing once per engineer–artist pair; it stays in place. You can remove a share any time in the admin console.

**For each session**, the engineer's start screen shows the address to give the artist, under **Over the internet (Tailscale)**. Tailscale must be connected on both Macs whenever you work together.

## Running a session

### Engineer

1. Open Pro Tools and your session, and **arm the artist's track** (see [Pro Tools setup](#pro-tools-setup-engineer-once)).
2. Double-click **Take Engineer.app**. The engineer app opens with a **session code**.
3. Send the artist the code. **Over the internet, also send your Tailscale address**, shown under the code.
4. When the artist joins, the **Artist** row in the engineer app shows **Connected**. Set their cue mix with the knobs. The artist hears the result; the engineer app doesn't play audio.
5. Press **Record** in Pro Tools. The artist sees a 3-2-1 countdown and their Mac starts recording. You hear the artist live through the armed track.
6. Press **Stop** in Pro Tools. A few seconds later the artist's lossless take appears in the engineer app's take list and is **swapped in** on the armed track, where the live preview was.

With **Auto-sync takes** turned off (engineer app ▸ Settings), takes wait in the list until you press **Sync now**.

If Pro Tools records a take the artist's Mac didn't capture (for example the artist wasn't connected yet), both apps show a red **Take not captured** warning. Only the live preview is on the track then; record it again.

### Artist

1. Double-click **Take Artist.app**.
2. Type the **session code** from the engineer. On the same network, press **Join session**; that's all.
3. Over the internet, click **Joining over the internet? Enter the engineer's address**, enter the Tailscale address the engineer sent, then **Join session**. If you try the code alone, the app tells you the engineer isn't on your network and asks for the address.
4. Put on headphones: you hear yourself through the cue mix, and the backing track when the engineer plays.
5. Perform when the countdown ends. The ring shows **REC** while your Mac is recording.

**End Session** disconnects only you. The session stays open, so you can join again with the same code until the engineer ends it.

**Your input:** Take records one input: the default input device's input 1, unless set otherwise. With an audio interface, set `TAKE_INPUT_DEVICE` to its name (or part of it) and `TAKE_INPUT_CHANNEL` to the input your mic is on (see [Settings](#settings)). Only that input is recorded, streamed and metered; other inputs are never mixed in.

## What Take does in your Pro Tools session

Take only acts when a take arrives, and only on the track that was armed when recording started:

- It clears the live preview recording of that take and places the lossless file where the artist's capture actually began. The file is imported through the clip list and converted to the session's sample rate if needed.
- In **Shuffle** mode, it switches to Slip for that edit and back afterwards, so no later clip moves.
- It checks the edit selection before clearing anything. With *Link Timeline and Edit Selection* off it doesn't clear; the take is placed on top of the preview instead.
- It never changes track inputs, routing, or arm state.

## Timing

The artist's backing track plays slightly *ahead* of Pro Tools, by the whole round trip: network, both Macs' audio latencies, the engineer's stream buffer and Pro Tools' input latency. That way the artist's live voice reaches Pro Tools in time with the session. Take works this out each time playback starts and keeps it fixed until playback stops.

To ride out network jitter, the live stream waits in a buffer on the engineer's Mac before it plays into Pro Tools: **40 ms** when the artist joined over the local network, **120 ms** over the internet. The size is chosen automatically when the artist joins. The internet figure comes from measurements on the single internet test so far; other connections may need a different size (`TAKE_STREAM_BUFFER_MS`).

The lossless take doesn't depend on any of this: it's placed sample-accurately from the artist's own recording.

## Settings

Take works without any configuration. To change something, set these environment variables in `~/.zshrc` (e.g. `export TAKE_INPUT_CHANNEL=2`), then open Take again. The launchers run in a Terminal window, which reads that file.

| Variable | Mac | Default | What it does |
|---|---|---|---|
| `TAKE_INPUT_DEVICE` | artist | system default input | Input device to record (its name, or part of it, e.g. `Scarlett`) |
| `TAKE_INPUT_CHANNEL` | artist | `1` | Which input of that device the mic is on |
| `TAKE_OUTPUT_DEVICE` | artist | system default output | Where the artist hears the cue mix |
| `TAKE_STREAM_DEVICE` | engineer | `Pro Tools Audio Bridge 2-A` | Virtual device Pro Tools records the live stream from |
| `TAKE_STREAM_BUFFER_MS` | engineer | 40 on a LAN, 120 over the internet | One fixed buffer size for every connection: more for a shaky connection, less for tighter monitoring |
| `TAKE_DAW_INPUT_OFFSET_MS` | engineer | `47` | Pro Tools' own input delay, part of the timing above. If you hear the artist consistently early or late against the session, change it by that many ms. It grows with Pro Tools' H/W buffer size. |
| `TAKE_RELAY_HOST` | artist | the address joined with | Development only: where the artist backend finds the engineer's relay |

## Troubleshooting

- **The artist can't join with the code.** Over the internet that's expected: enter the engineer's Tailscale address as well. On the same network, check both Macs really are on the same network. Some guest or office Wi-Fi blocks devices from finding each other; use the address there too (the engineer's start screen shows the local one as well).
- **"Can't reach that address."** Check Tailscale shows **Connected** on both Macs and that both Macs are shared with each other ([Tailscale](#connecting-over-the-internet-tailscale), steps 5–8). Then try `ping <address>` from Terminal.
- **Joined, but no audio or takes arrive.** On each Mac, check that **System Settings ▸ Network ▸ Firewall** allows incoming connections for Python, or turn the firewall off during sessions.
- **The artist app says "Take backend not running."** Open **Take Artist.app** (the launcher in the `Take` folder), not `Take.app` directly. The launcher starts the backend that does the recording.
- **"Port conflict — cannot start."** Another copy of Take is still running. Close its Terminal window (or quit the process `lsof -i :PORT` shows), then open Take again.
- **Pro Tools records silence on the artist's track.** Check the track's input is Audio Bridge 2-A channel 1 through an aggregate Playback Engine, not Audio Bridge as the engine itself ([Pro Tools setup](#pro-tools-setup-engineer-once)).
- **Logs** are in the `logs/` folder (`engineer.log`, `electron.log`, `artist.log`). `logs/tail_logs.sh` follows them live.

## Known limitations

- **Internet sessions are experimental.** Tested only by one person operating both Macs on two networks, not yet by two people in two locations (see the testing status at the top).
- **Take doesn't press Record in Pro Tools.** The engineer does; Take follows.
- **Pro Tools' scripting interface can't read the playhead.** Take works out positions from when the transport started. The backing-track sync doesn't follow loops, pre-roll, scrubbing or seeking while the transport rolls. Pro Tools also reports "playing" only to within about ±15–20 ms of when its audio starts, so what the engineer hears lines up to within that. Takes are unaffected: they're placed sample-accurately.
- **Backing track:** the backend can bounce the session mix to MP3 and send it to the artist (bounce service on port 5006), but the engineer app has no button for it yet.
- **Not yet tested:** pre-roll, loop record, QuickPunch, Shuffle mode, *Link Timeline and Edit Selection* turned off.
- A congested connection (for example a phone hotspot) can stall for longer than the 120 ms buffer covers. The live preview then drops out briefly; the lossless take is unaffected.

## For developers

**Layout**

```
Take/
├── Take Engineer.app   Engineer launcher: first-run setup, relay + backend, engineer app
├── Take Artist.app     Artist launcher: first-run setup, backend, artist app
├── artist-app/         Artist app (JUCE / C++). prebuilt/Take.app is the committed build a clone runs
├── engineer-app/       Engineer app (Electron + React + Vite)
├── backend/            Python services for both sides (relay, transport, streaming, file transfer, Pro Tools)
├── docs/               artist-window.html: the artist app's design reference
├── logs/               Runtime logs (git-ignored) and tail_logs.sh
├── recordings/         Artist's lossless takes (git-ignored)
├── incoming/           Takes the engineer has received (git-ignored)
├── PORTS.md            Port map
└── CLAUDE.md           Project decisions and constraints for contributors
```

Both halves of `backend/` live in one folder because they share modules (file transfer, timecode). Everything DAW-specific is behind `backend/daw.py`; the implementation in use is `backend/pro_tools.py`, which drives Pro Tools through PTSL (gRPC on `localhost:31416`) with [py-ptsl](https://github.com/iluvcapra/py-ptsl) 601.1.0, the newest release that supports Python 3.9.

**Running by hand**

```bash
cd backend && ./dev_engineer.sh        # relay + engineer backend
cd engineer-app && npm run start       # engineer app
cd backend && ./dev_artist.sh          # artist backend (then open artist-app/prebuilt/Take.app)
```

**Ports:** see [PORTS.md](PORTS.md). The engineer's Mac must be reachable from the artist's on 5001, 5002 and 5010, and the artist's from the engineer's on 5003–5005, 5007 and 5009. Each startup script checks its ports and says which one is taken.

**Changing the artist app:** open `artist-app/Take/Take.jucer` in Projucer or the Xcode project in `artist-app/Take/Builds/MacOSX`. Afterwards run `artist-app/build_prebuilt.sh` and commit `artist-app/prebuilt/Take.app` with the change: a fresh clone runs that build. Never commit Xcode's `build/` folder.

## Legacy: Reaper

Take was first built on Reaper, controlled by a Lua script (`take_session.lua`) through files, because Reaper's web API returned 404 on the setup it was developed on. That version is preserved on the [`reaper`](https://github.com/smeyl/Take/tree/reaper) branch. It isn't maintained or supported.

On `main`, `backend/reaper.py` and `backend/take_session.lua` remain only as a reference implementation of the same DAW interface as `pro_tools.py`. `daw.py` always uses Pro Tools. `setup.sh` installs the Lua script only if Reaper happens to be installed. Some relay routes are still named `/reaper/…` for historical reasons; they drive whichever DAW `daw.py` uses.

## Built with

- **[JUCE](https://juce.com/)**: the artist app (C++)
- **[Electron](https://www.electronjs.org/)** + React + Vite: the engineer app
- **[Python](https://www.python.org/)**: the services on both Macs
- **[Pro Tools](https://www.avid.com/pro-tools)** + **PTSL** via **[py-ptsl](https://github.com/iluvcapra/py-ptsl)**: the engineer's DAW
- **[Tailscale](https://tailscale.com)**: connecting the two Macs over the internet

## License

Take's own code is released under the [MIT License](LICENSE). Copyright (c) 2026 Arda Akıncı.

**Third-party licences.** Take is built on software under its own licences:

- **JUCE 8** (the artist app) is dual-licensed under AGPLv3 and the [JUCE 8 licence](https://juce.com/legal/juce-8-licence/). The committed artist app is built under the JUCE licence. If you build or distribute the artist app yourself, you need either a JUCE licence of your own (the free Starter tier covers up to $20,000 a year in revenue) or to use JUCE under AGPLv3, which then applies to the app you distribute.
- **[pedalboard](https://github.com/spotify/pedalboard)** (the artist's cue-mix effects) is **GPLv3**. Take doesn't include it; `setup.sh` installs it. If you distribute Take together with pedalboard, that bundle is subject to GPLv3.
- **IBM Plex Mono** (the artist app's font) is under the [SIL Open Font License 1.1](artist-app/Take/Resources/Fonts/OFL.txt).
- py-ptsl (BSD-3-Clause), Flask, flask-cors, requests, PyAudio, sounddevice, soundfile, watchdog, numpy, Electron and React are under permissive licences (BSD, MIT, Apache 2.0).
- Pro Tools, PTSL and the Pro Tools Audio Bridge are Avid products and aren't part of Take.
