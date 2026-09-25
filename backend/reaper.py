"""Reaper implementation of the DAW interface in daw.py — import daw, not this.

All Reaper control is file-based IPC with take_session.lua — auto-started
with Reaper via __startup.lua (see setup.sh). The Reaper web API returns 404
on this setup, so nothing here may depend on HTTP calls to Reaper.
"""
import json
import os
import time

NAME = "Reaper"
STREAM_DEVICE = "BlackHole"  # Reaper's recording track takes its input from BlackHole

CMD_FILE   = "/tmp/take_reaper_cmd"
START_FILE = "/tmp/take_record_start"  # written by Lua when recording starts
BOUNCE_DONE_FILE = "/tmp/take_bounce_done"  # written by Lua when a render finishes
TRACKS_FILE    = "/tmp/take_tracks.json"     # kept current by take_session.lua
MARKERS_FILE   = "/tmp/take_markers.json"    # kept current by take_session.lua
TRANSPORT_FILE = "/tmp/take_transport.json"  # rewritten ≥1/s — doubles as liveness

# take_session.lua force-writes TRANSPORT_FILE every second; a stale mtime
# means the script (or Reaper) is not running.
SCRIPT_ALIVE_MAX_AGE = 5.0  # seconds
# Swap info left over from a crashed/killed session must not place a new take
# at an old position — anything older than this is treated as gone.
START_MAX_AGE = 3600  # seconds


def _write_cmd(lines):
    # Write-then-rename so take_session.lua (polling ~30x/s) can never read a
    # half-written command file. rename() is atomic on the same filesystem.
    tmp = CMD_FILE + ".tmp"
    try:
        with open(tmp, "w") as f:
            f.write("\n".join(str(l) for l in lines) + "\n")
        os.replace(tmp, CMD_FILE)
    except OSError as e:
        print(f"  ERROR: could not write Reaper command: {e}")


def _read_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def stream_device():
    return STREAM_DEVICE


def alive():
    """True if take_session.lua is running (its transport export is fresh)."""
    try:
        return time.time() - os.path.getmtime(TRANSPORT_FILE) < SCRIPT_ALIVE_MAX_AGE
    except OSError:
        return False


def get_transport():
    """Current Reaper transport as (position_seconds, playing). Falls back to
    (0.0, False) when the export is missing — callers treat that as stopped."""
    data = _read_json(TRANSPORT_FILE, {})
    try:
        return float(data.get("pos", 0.0)), bool(data.get("playing", False))
    except (TypeError, ValueError):
        return 0.0, False


def is_recording():
    """True while Reaper's transport is recording, per take_session.lua's
    export. False when the export is missing or predates the flag."""
    return bool(_read_json(TRANSPORT_FILE, {}).get("recording", False))


def get_markers():
    return _read_json(MARKERS_FILE, [])


def get_tracks():
    return _read_json(TRACKS_FILE, [])


def get_track_count():
    return len(get_tracks())


def start_recording(track=0, capture_pos=None):
    # take_session.lua arms the track and starts the transport (it places
    # takes itself, so capture_pos isn't used)
    _write_cmd(["record", track])
    return True


def stop_recording():
    _write_cmd(["stop"])
    return True


def insert_media(filepath, track=0):
    """Place a file on a track at the edit cursor (fallback when no swap
    position is known). Handled by take_session.lua."""
    _write_cmd(["insert", filepath, track])
    return True


def start_bounce(selected_tracks=None):
    """Ask take_session.lua to render the project to a unique MP3 in /tmp.
    selected_tracks: iterable of track indices to include (all others are
    muted for the render); None/empty = include everything. Clears the prior
    done-signal so the caller detects the new one."""
    try:
        os.remove(BOUNCE_DONE_FILE)
    except OSError:
        pass
    csv = ",".join(str(int(i)) for i in (selected_tracks or []))
    _write_cmd(["bounce", csv])
    return True


def bounce_signalled():
    """True once take_session.lua has finished the render for start_bounce()."""
    return os.path.exists(BOUNCE_DONE_FILE)


def bounce_output_path():
    """The rendered file's path, as reported by take_session.lua in the
    done-signal file. None until bounce_signalled() is True."""
    try:
        with open(BOUNCE_DONE_FILE) as f:
            path = f.readline().strip()
        return path or None
    except OSError:
        return None


def return_to_zero():
    _write_cmd(["rtz"])
    return True


def place_take(filepath, fallback_track=0):
    """Swap the lossless take in for the streamed recording, else insert it on
    fallback_track. Returns "swapped", "inserted" or "not_running"."""
    filename = os.path.basename(filepath)
    # Try file swap: replace the BlackHole-recorded stream item with the lossless file.
    # Requires take_session.lua running in Reaper and a prior recording in this session.
    try:
        age = time.time() - os.path.getmtime(START_FILE)
        if age > START_MAX_AGE:
            os.remove(START_FILE)
            print(f"[sync] discarding stale swap info ({age:.0f}s old) — "
                  f"falling back to insert")
            raise FileNotFoundError(START_FILE)
        with open(START_FILE) as f:
            lines = f.read().strip().split("\n")
        start_time = float(lines[0])
        track_idx  = int(lines[1]) if len(lines) > 1 else 0
        print(f"[sync] swap info: track {track_idx}, position {start_time:.3f}s "
              f"(from {START_FILE})")
        # Atomic write via _write_cmd — never a partial read in Lua
        _write_cmd(["swap", filepath, track_idx, f"{start_time:.6f}"])
        # Consume the start info so a later, unrelated file can't swap onto
        # this take's position — it falls through to a plain insert instead.
        os.remove(START_FILE)
        print(f"[sync] swap queued for take_session.lua — {filename}")
        return "swapped"
    except FileNotFoundError:
        print(f"[sync] no swap info ({START_FILE} missing — no recording "
              f"this session, or already consumed) — falling back to insert")
    except Exception as e:
        print(f"[sync] swap failed ({e}) — falling back to insert")

    # Fallback: insert as a new item on fallback_track at the edit cursor
    # (used before the first recording of a session).
    if not alive():
        print(f"[sync] take_session.lua is not running — {filename} NOT placed "
              f"in Reaper. Start Reaper (the Take script loads automatically) "
              f"and use Sync now.")
        return "not_running"
    insert_media(filepath, fallback_track)
    print(f"[sync] insert queued for take_session.lua — {filename} on track {fallback_track}")
    return "inserted"


if __name__ == "__main__":
    running = alive()
    pos, playing = get_transport()
    print(f"take_session.lua : {'running' if running else 'NOT RUNNING'}")
    print(f"transport        : {pos:.3f}s {'playing' if playing else 'stopped'}")
    print(f"tracks           : {get_track_count()}")
    print(f"markers          : {len(get_markers())}")
