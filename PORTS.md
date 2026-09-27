# Take — Port Map

All services bind `0.0.0.0`. "Machine" is where the service runs in a
two-machine session; in single-machine dev everything shares localhost.

| Port | Proto | Service                  | Machine  | Direction / purpose                                      |
|------|-------|--------------------------|----------|----------------------------------------------------------|
| 5001 | TCP   | Take receiver (Flask)    | engineer | Artist → engineer: lossless takes. Hosts the swap logic (`engineer.py`), so it must be the engineer's process — hence its own port. |
| 5002 | UDP   | Artist mic stream        | engineer | Artist mic audio → BlackHole only (Reaper live input; the engineer monitors through Reaper). 1-byte format header + PCM. |
| 5003 | UDP   | Cue params               | artist   | Engineer's cue-mix knob changes → artist DSP (`cue_receiver.py`). |
| 5004 | TCP   | Transport (Flask)        | artist   | Record/stop/status/levels. Reached by the engineer UI through the relay proxy. |
| 5005 | UDP   | Timecode                 | artist   | Engineer (Reaper playhead) → artist backing-track sync.   |
| 5006 | TCP   | Bounce server (Flask)    | engineer | Engineer UI triggers Reaper render + send to artist.      |
| 5007 | TCP   | Stream quality (Flask)   | artist   | Engineer UI sets mic stream encoding (PCM16/PCM24/Float32) via relay proxy. |
| 5009 | TCP   | Backing receiver (Flask) | artist   | Engineer → artist: bounced backing track. Same code as 5001 (`receiver.py`) on a separate port, so both can run on one machine in dev. |
| 5010 | TCP   | Relay (Flask)            | engineer | Session codes, heartbeats, timecode/punch state, artist-machine proxy, Reaper transport commands. |
| 5011 | UDP   | Relay discovery          | engineer | Artist broadcasts `TAKE_DISCOVER_V1:<code>`; relay replies with its own IP so the artist joins with just the code — no manual IP. Optional: if broadcasts are blocked (e.g. across Tailscale) or the port is taken, the artist enters the engineer's address instead — shown on the engineer's start screen; the relay still starts and warns. |
| 8080 | TCP   | Reaper web interface     | engineer | Reaper's own web control API. Not bound and no longer used by Take — all Reaper control is file-based Lua IPC (`take_session.lua`). |

## Conflict detection

`start_engineer.py`, `start_artist.py`, and `relay.py` check their ports at
startup via `backend/ports.py` and exit with a clear message if one is
taken (`lsof -i :PORT` finds the offender). The engineer (5001) and artist
(5009) file receivers use separate ports specifically so single-machine dev
never produces a silent collision.
