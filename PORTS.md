# Take — Port Map

All services bind `0.0.0.0`. "Machine" is where the service runs in a
two-machine session; in single-machine dev everything shares localhost.

Over the internet the two Macs reach each other through Tailscale
(`100.x` addresses). Each Mac must be shared with the other (see the
README), because connections start from both sides:

- **artist → engineer:** 5001, 5002, 5010 (and 5011, LAN only)
- **engineer → artist:** 5003, 5004, 5005, 5007, 5009

A macOS firewall on either Mac must allow incoming connections for Python.

| Port | Proto | Service                  | Machine  | Direction / purpose                                      |
|------|-------|--------------------------|----------|----------------------------------------------------------|
| 5001 | TCP   | Take receiver (Flask)    | engineer | Artist → engineer: lossless takes. Hosts the swap logic (`engineer.py`), so it must be the engineer's process — hence its own port. |
| 5002 | UDP   | Artist mic stream        | engineer | Artist mic audio (44.1 kHz, 1-byte format header + PCM) → a fixed jitter buffer → Pro Tools Audio Bridge 2-A (`TAKE_STREAM_DEVICE`), which Pro Tools records and monitors on the armed track. Monitoring only — the lossless take replaces that recording. |
| 5003 | UDP   | Cue params               | artist   | Engineer's cue-mix knob changes → artist DSP (`cue_receiver.py`). |
| 5004 | TCP   | Transport (Flask)        | artist   | Record/stop/status/levels, and the artist leaving a session (`/session/leave`, the artist app's End Session). Reached by the engineer UI through the relay proxy; the artist app polls it locally. |
| 5005 | UDP   | Timecode                 | artist   | Engineer → artist: Pro Tools transport position/state (backing-track sync) and the engineer's cursor (live marker). |
| 5006 | TCP   | Bounce server (Flask)    | engineer | Engineer UI triggers a Pro Tools mix bounce (MP3) + send to artist. |
| 5007 | TCP   | Stream quality (Flask)   | artist   | Engineer UI sets mic stream encoding (PCM16/PCM24/Float32) via relay proxy. |
| 5009 | TCP   | Backing receiver (Flask) | artist   | Engineer → artist: bounced backing track. Same code as 5001 (`receiver.py`) on a separate port, so both can run on one machine in dev. |
| 5010 | TCP   | Relay (Flask)            | engineer | Session codes, joins and leaves, heartbeats, timecode state, missed-take list, artist-machine proxy, DAW commands (the `/reaper/*` route names are historical — they drive Pro Tools). Tells the artist which address to send to: the one they reached it on. |
| 5011 | UDP   | Relay discovery          | engineer | Artist broadcasts `TAKE_DISCOVER_V1:<code>`; relay replies with its own IP so the artist joins with just the code — no manual IP. Optional: if broadcasts are blocked (e.g. across Tailscale) or the port is taken, the artist enters the engineer's address instead — shown on the engineer's start screen; the relay still starts and warns. |
| 31416 | TCP  | PTSL (gRPC)             | engineer | Run by Pro Tools itself on `localhost` while it's open; Take's backend (`pro_tools.py`) controls Pro Tools through it. Not bound by Take. |
| 8080 | TCP   | Reaper web interface     | engineer | Legacy Reaper integration only (`reaper` branch): Reaper's own web API, not bound or used by Take — Reaper was controlled by file-based Lua IPC. |

## Conflict detection

`start_engineer.py`, `start_artist.py`, and `relay.py` check their ports at
startup via `backend/ports.py` and exit with a clear message if one is
taken (`lsof -i :PORT` finds the offender). The check binds the way the
services do (TCP with `SO_REUSEADDR`, as Flask does), so restarting right
after a stop isn't refused because of the old connections' TIME_WAIT
sockets, while a port another process is listening on still is. The engineer (5001) and artist
(5009) file receivers use separate ports specifically so single-machine dev
never produces a silent collision.
