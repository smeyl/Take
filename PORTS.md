# Take — Port Map

All services bind `0.0.0.0`. "Machine" is where the service runs in a
two-machine session; in single-machine dev everything shares localhost.

| Port | Proto | Service                  | Machine  | Direction / purpose                                      |
|------|-------|--------------------------|----------|----------------------------------------------------------|
| 5001 | TCP   | File receiver (Flask)    | both     | Artist → engineer: lossless takes. Engineer → artist: bounced backing track. Same code (`receiver.py`), one instance per machine. |
| 5002 | UDP   | Artist mic stream        | engineer | Artist mic audio → engineer speakers + BlackHole (Reaper live input). 1-byte format header + PCM. |
| 5003 | UDP   | Cue params               | artist   | Engineer's cue-mix knob changes → artist DSP (`cue_receiver.py`). |
| 5004 | TCP   | Transport (Flask)        | artist   | Record/stop/status/levels. Reached by the engineer UI through the relay proxy. |
| 5005 | UDP   | Timecode                 | artist   | Engineer (Reaper playhead) → artist backing-track sync.   |
| 5006 | TCP   | Bounce server (Flask)    | engineer | Engineer UI triggers Reaper render + send to artist.      |
| 5007 | TCP   | Stream quality (Flask)   | artist   | Engineer UI sets mic stream encoding (PCM16/PCM24/Float32) via relay proxy. |
| 5010 | TCP   | Relay (Flask)            | engineer | Session codes, heartbeats, timecode/punch state, artist-machine proxy, Reaper transport commands. |
| 8080 | TCP   | Reaper web interface     | engineer | Reaper's own web control API (enable in Reaper preferences). Not bound by Take. |

## Conflict detection

`start_engineer.py`, `start_artist.py`, and `relay.py` check their ports at
startup via `companion-app/ports.py` and exit with a clear message if one is
taken (`lsof -i :PORT` finds the offender). Port 5001 on the artist machine is
exempt: in single-machine dev the engineer's receiver already owns it, which
`start_artist.py` treats as expected.
