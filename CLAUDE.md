# CLAUDE.md

Guidance for Claude Code (and any future session) working in this repo. These
are **locked** decisions — treat them as constraints, not suggestions. If a task
seems to require breaking one, stop and ask rather than working around it.

## Project summary

Take is a remote recording session tool that lets an engineer and an artist
collaborate from different locations. The engineer records in Pro Tools as
usual — Take follows Pro Tools' Record/Stop, it never presses them — and sets
the artist's cue mix and receives takes in a desktop app (Electron + React).
The artist monitors session state and meters in a native macOS app (JUCE /
C++). Each take is captured losslessly on the artist's machine and transferred
back, then swapped into Pro Tools in place of the live-streamed preview. The
Python `backend/` holds the services for both sides. README.md is the user
guide (setup, Tailscale, Pro Tools routing); PORTS.md the port map.

## Locked architecture decisions

- **Pro Tools is the target DAW.** `main` supports Pro Tools only, controlled
  via PTSL (the Pro Tools Scripting Library, gRPC). Reaper support was
  reference/legacy work and is preserved on the `reaper` branch; it is not the
  direction `main` is going.
- **DAW-agnostic core behind `backend/daw.py`.** The rest of the backend imports
  `daw`, never a specific DAW module. Each DAW integration (`pro_tools.py`, and
  the legacy `reaper.py`) implements the same functions; `daw.py` picks the
  active one. Don't hard-wire one DAW's assumptions into the core.
- **Tailscale for internet connectivity, NOT WebRTC.** Cross-location sessions
  run over Tailscale. Do not introduce WebRTC, STUN/TURN, or peer signaling.
- **Local-record-and-transfer.** Audio is recorded losslessly on the artist's
  machine and the finished takes are transferred to the engineer afterward. We
  do not stream lossless audio live for capture — the mic stream (UDP 5002) is
  monitoring only; the recording is the local file.
- **Legacy Reaper integration: file-based Lua IPC.** Where the Reaper code is
  touched (`reaper.py`, `take_session.lua`), Reaper is controlled via file-based
  Lua scripts, NOT its web control API — the Reaper web API returns **404 on
  this setup**. Port 8080 is Reaper's own web interface and is not bound by
  Take.

## Anti-scope-creep rules

- **No Logic or Ableton support.** Pro Tools is the target; Reaper stays only
  as the legacy reference implementation.
- **No installer, no code-signing, no notarization.** Distribution is out of
  scope. Do not add packaging/signing pipelines.
- **No new features that weren't explicitly requested.** Implement what's asked,
  nothing more. If you spot an adjacent improvement, mention it — don't build it.

## Port map

See **[PORTS.md](PORTS.md)** for the authoritative port map. All services bind
`0.0.0.0`; startup conflict detection lives in `backend/ports.py`. When adding
or changing a port, update PORTS.md in the same change.

## Housekeeping rules for Claude Code

- **Delete temporary/generated files when the task is done.** Scripts written
  only to generate other files, intermediate build artifacts, scratch files —
  clean them up unless the user explicitly asked to keep them.
- **Never leave debug print statements in committed code.** Remove `print(...)` /
  `console.log(...)` debugging before considering a change done.
- **After changing the artist app (JUCE), refresh the committed build:** run
  `artist-app/build_prebuilt.sh` and commit `artist-app/prebuilt/Take.app` with
  the source change. A fresh clone runs that committed app — artists don't
  have Xcode or JUCE — so a stale one ships old behaviour.
- **Only source, docs and the prebuilt artist app are committed.** Never
  commit Xcode's `build/` folders, recordings, takes, logs or other generated
  binaries. (The README's screenshots in `docs/screenshots/` are fine: keep
  them small, and free of IP addresses or other personal details.) History was rewritten on 2026-09-27 to remove ~140 MB of exactly
  that (old Debug builds, test recordings); `artist-app/prebuilt/Take.app` is
  the one binary that belongs in git.
- **Test changes before declaring them done, whenever possible.** Run the
  affected path (or at least the relevant script/build) and report the actual
  result. If you couldn't test something, say so plainly.

## Known environment facts

- **Python 3.9 at `/usr/bin/python3`** (system Python on this Mac). The backend
  scripts target this interpreter.
- **`pedalboard` requires Python ≤ 3.12.** Do not assume/require Python 3.13+.
- **macOS app bundles must launch via `osascript` + Terminal, not direct exec.**
  Gatekeeper blocks directly executing the bundled scripts; the `.app` bundles
  (`Take Engineer.app`, `Take Artist.app`) use `osascript` to open Terminal and
  run from there. Keep this pattern when touching the bundles.
