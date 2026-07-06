# CLAUDE.md

Guidance for Claude Code (and any future session) working in this repo. These
are **locked** decisions — treat them as constraints, not suggestions. If a task
seems to require breaking one, stop and ask rather than working around it.

## Project summary

Take is a remote recording session tool that lets an engineer and an artist
collaborate from different locations. The engineer controls transport and cue
mix from a web app (Electron + React); the artist monitors session state and
meters in a native macOS app (JUCE / C++). Recording is captured losslessly on
the artist's machine and the takes are transferred back to the engineer, with
Reaper driving the actual capture. The Python `backend/` holds the services for
both sides.

## Locked architecture decisions

- **DAW-agnostic core, Reaper as the showcase.** The core is not tied to any
  one DAW. Reaper is the reference/showcase integration — build against a clean
  seam, don't hard-wire Reaper assumptions into the core.
- **Tailscale for internet connectivity, NOT WebRTC.** Cross-location sessions
  run over Tailscale. Do not introduce WebRTC, STUN/TURN, or peer signaling.
- **Local-record-and-transfer.** Audio is recorded losslessly on the artist's
  machine and the finished takes are transferred to the engineer afterward. We
  do not stream lossless audio live for capture — the mic stream (UDP 5002) is
  monitoring only; the recording is the local file.
- **File-based Lua IPC with Reaper.** Reaper is controlled via file-based Lua
  scripts, NOT its web control API. The Reaper web API returns **404 on this
  setup**, so do not build features that depend on HTTP calls to Reaper. Port
  8080 is Reaper's own web interface and is not bound by Take.

## Anti-scope-creep rules

- **No Logic or Ableton support.** Reaper only. Do not add other DAW backends.
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
