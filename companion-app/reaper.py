import time
import requests

# Requires Reaper web server enabled:
# Reaper > Preferences > Control/OSC/web > Add > Web browser interface
BASE = "http://localhost:8080"

# Action IDs — verify or reassign via Reaper: Actions > Show Action List
ACTION_INSERT_TRACK = 40001  # Track: Insert new track
ACTION_RECORD       = 1013   # Transport: Record
ACTION_STOP         = 1016   # Transport: Stop

ACTION_SELECT_LAST_TRACK = 40297  # Track: Select last track
ACTION_ARM_TRACK         = 9      # Track: Toggle record arm for selected track

# File-based IPC for transport control (web API action endpoints return 404 on this machine).
# take_reaper_poll.lua must be running in Reaper (Actions > Run script...).
CMD_FILE   = "/tmp/take_reaper_cmd"
START_FILE = "/tmp/take_record_start"  # written by Lua when recording starts

_pending_track = 0  # track stored by arm_track_by_index(), read by start_recording()


def _write_cmd(lines):
    try:
        with open(CMD_FILE, "w") as f:
            f.write("\n".join(str(l) for l in lines) + "\n")
    except OSError as e:
        print(f"  ERROR: could not write Reaper command: {e}")


def _get(path, timeout=5):
    url = f"{BASE}{path}"
    try:
        r = requests.get(url, timeout=timeout)
        return r.status_code
    except requests.RequestException:
        print("  ERROR: Could not connect — is Reaper running with the web server enabled?")
        return None


def _get_text(path, timeout=5):
    url = f"{BASE}{path}"
    try:
        r = requests.get(url, timeout=timeout)
        text = r.text.strip()
        return text if r.status_code == 200 else None
    except Exception:
        return None


MARKERS_FILE = "/tmp/take_markers.json"

def get_markers():
    # Populated by take_export_markers.lua — run it in Reaper via
    # Actions → Run ReaScript → take_export_markers.lua whenever the project changes.
    import json, os
    if not os.path.exists(MARKERS_FILE):
        return []
    try:
        with open(MARKERS_FILE) as f:
            return json.load(f)
    except Exception:
        return []


TRACKS_FILE = "/tmp/take_tracks.json"

def get_tracks():
    # Populated by take_export_tracks.lua — run it in Reaper via
    # Actions → Run ReaScript → take_export_tracks.lua whenever the project changes.
    import json, os
    if not os.path.exists(TRACKS_FILE):
        return []
    try:
        with open(TRACKS_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def get_track_count():
    return len(get_tracks())


def arm_track_by_index(n):
    """Store track index for use by start_recording() — arming happens atomically in Lua."""
    global _pending_track
    _pending_track = n


def get_track_muted(index):
    return _get_text(f"/GET/TRACK/{index}/B_MUTE") == "1"


def set_track_muted(index, muted):
    _get(f"/SET/TRACK/{index}/B_MUTE/{'1' if muted else '0'}")


def create_track():
    status = _get(f"/_/{ACTION_INSERT_TRACK}")
    _get(f"/_/{ACTION_SELECT_LAST_TRACK}")
    return status == 200


def arm_track():
    return _get(f"/_/{ACTION_ARM_TRACK}") == 200


def start_recording():
    _write_cmd(["record", _pending_track])
    return True


def unarm_track():
    return _get(f"/_/{ACTION_ARM_TRACK}") == 200


def stop_recording():
    _write_cmd(["stop"])
    return True


def return_to_zero():
    _write_cmd(["rtz"])
    return True


if __name__ == "__main__":
    print(f"Connecting to Reaper at {BASE}\n")

    create_track()
    time.sleep(0.5)

    arm_track()
    time.sleep(0.5)

    start_recording()
    print("Recording for 3 seconds...")
    time.sleep(3)

    stop_recording()
    unarm_track()
