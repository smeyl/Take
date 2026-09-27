# Take — Port Map

All services bind `0.0.0.0`. "Machine" is where the service runs in a
two-machine session; in single-machine dev everything shares localhost.

| Port | Proto | Service                  | Machine  | Direction / purpose                                      |
|------|-------|--------------------------|----------|----------------------------------------------------------|
| 5001 | TCP   | Take receiver (Flask)    | engineer | Artist → engineer: lossless takes. Hosts the swap logic (`engineer.py`), so it must be the engineer's process — hence its own port. |
| 5002 | UDP   | Artist mic stream        | engineer | Artist mic audio (44.1 kHz, 1-byte format header + PCM) → a fixed jitter buffer → Pro Tools Audio Bridge 2-A (`TAKE_STREAM_DEVICE`), which Pro Tools records and monitors on the armed track. Monitoring only — the lossless take replaces that recording. |
| 5003 | UDP   | Cue params               | artist   | Engineer's cue-mix knob changes → artist DSP (`cue_receiver.py`). |
| 5004 | TCP   | Transport (Flask)        | artist   | Record/stop/status/levels. Reached by the engineer UI through the relay proxy. |
| 5005 | UDP   | Timecode                 | artist   | Engineer → artist: Pro Tools transport position/state (backing-track sync) and the engineer's cursor (live marker). |
| 5006 | TCP   | Bounce server (Flask)    | engineer | Engineer UI triggers a Pro Tools mix bounce (MP3) + send to artist. |
| 5007 | TCP   | Stream quality (Flask)   | artist   | Engineer UI sets mic stream encoding (PCM16/PCM24/Float32) via relay proxy. |
| 5009 | TCP   | Backing receiver (Flask) | artist   | Engineer → artist: bounced backing track. Same code as 5001 (`receiver.py`) on a separate port, so both can run on one machine in dev. |
| 5010 | TCP   | Relay (Flask)            | engineer | Session codes, heartbeats, timecode state, artist-machine proxy, DAW commands (record/stop — the `/reaper/*` route names are historical). Tells the artist which address to send to: the one they reached it on. |
| 5011 | UDP   | Relay discovery          | engineer | Artist broadcasts `TAKE_DISCOVER_V1:<code>`; relay replies with its own IP so the artist joins with just the code — no manual IP. Optional: if broadcasts are blocked (e.g. across Tailscale) or the port is taken, the artist enters the engineer's address instead — shown on the engineer's start screen; the relay still starts and warns. |
| 8080 | TCP   | Reaper web interface     | engineer | Legacy Reaper integration only (`reaper` branch): Reaper's own web API, not bound or used by Take — Reaper was controlled by file-based Lua IPC. Pro Tools is controlled over PTSL (gRPC, `localhost:31416`, run by Pro Tools itself). |

## Conflict detection

`start_engineer.py`, `start_artist.py`, and `relay.py` check their ports at
startup via `backend/ports.py` and exit with a clear message if one is
taken (`lsof -i :PORT` finds the offender). The engineer (5001) and artist
(5009) file receivers use separate ports specifically so single-machine dev
never produces a silent collision.
