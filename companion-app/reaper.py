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


def _get(path, timeout=5):
    url = f"{BASE}{path}"
    try:
        r = requests.get(url, timeout=timeout)
        return r.status_code
    except requests.ConnectionError:
        print("  ERROR: Could not connect — is Reaper running with the web server enabled?")
        return None


def _get_text(path, timeout=5):
    try:
        r = requests.get(f"{BASE}{path}", timeout=timeout)
        return r.text.strip() if r.status_code == 200 else None
    except requests.ConnectionError:
        return None


def get_tracks():
    count_text = _get_text("/GET/TRACK/COUNT")
    if count_text is None:
        return []
    try:
        count = int(count_text)
    except ValueError:
        return []
    tracks = []
    for i in range(count):
        name = _get_text(f"/GET/TRACK/{i}/P_NAME") or f"Track {i + 1}"
        tracks.append({"index": i, "name": name})
    return tracks


def get_track_count():
    text = _get_text("/GET/TRACK/COUNT")
    try:
        return int(text) if text else 0
    except ValueError:
        return 0


def get_track_muted(index):
    return _get_text(f"/GET/TRACK/{index}/B_MUTE") == "1"


def set_track_muted(index, muted):
    _get(f"/SET/TRACK/{index}/B_MUTE/{'1' if muted else '0'}")


def create_track():
    status = _get(f"/_/{ACTION_INSERT_TRACK}")
    print(f"create_track   : {'OK' if status == 200 else 'FAILED'} (HTTP {status})")
    sel_status = _get(f"/_/{ACTION_SELECT_LAST_TRACK}")
    print(f"select_track   : {'OK' if sel_status == 200 else 'FAILED'} (HTTP {sel_status})")
    return status == 200


def arm_track():
    status = _get(f"/_/{ACTION_ARM_TRACK}")
    ok = status == 200
    print(f"arm_track      : {'OK' if ok else 'FAILED'} (HTTP {status})")
    return ok


def start_recording():
    status = _get(f"/_/{ACTION_RECORD}")
    ok = status == 200
    print(f"start_recording: {'OK' if ok else 'FAILED'} (HTTP {status})")
    return ok


def unarm_track():
    status = _get(f"/_/{ACTION_ARM_TRACK}")
    ok = status == 200
    print(f"unarm_track    : {'OK' if ok else 'FAILED'} (HTTP {status})")
    return ok


def stop_recording():
    status = _get(f"/_/{ACTION_STOP}", timeout=15)
    ok = status == 200
    print(f"stop_recording : {'OK' if ok else 'FAILED'} (HTTP {status})")
    return ok


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
