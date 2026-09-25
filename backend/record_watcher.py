"""Follow the DAW's own transport: when the engineer hits Record in the DAW,
start the artist's lossless capture; when they stop, stop it.

Makes exactly the calls the engineer app's old Rec/Stop button made — the
relay's /artist/record and /artist/stop — so the artist side runs its usual
countdown, capture, stop and file transfer. Runs on the engineer's machine,
next to the DAW and the relay. DAW-agnostic: it only asks daw.py whether the
DAW is reachable and recording.
"""
import threading
import time

import requests

import daw

RELAY_URL = "http://127.0.0.1:5010"
POLL_INTERVAL = 0.05  # seconds — same cadence as timecode.sender


def _trigger(endpoint):
    """POST the relay's /artist/<endpoint>. Returns (ok, detail)."""
    try:
        r = requests.post(f"{RELAY_URL}/artist/{endpoint}", timeout=5)
    except requests.RequestException as e:
        print(f"{daw.NAME} → artist {endpoint} failed: {e}", flush=True)
        return False, "the relay couldn't be reached"
    print(f"{daw.NAME} {'started' if endpoint == 'record' else 'stopped'} "
          f"recording → artist {endpoint}: HTTP {r.status_code}", flush=True)
    if r.ok:
        return True, ""
    try:
        detail = (r.json().get("error") or r.text).strip()
    except ValueError:
        detail = r.text.strip()
    if r.status_code == 404 and "not connected" in detail:
        return False, "the artist hadn't joined the session yet"
    if r.status_code == 502:
        return False, "the artist's machine couldn't be reached"
    if r.status_code == 409:
        return False, "the artist was already recording"
    return False, f"the artist's side refused to start recording ({r.status_code}: {detail})"


def _artist_recording():
    """True/False from the artist's transport (via the relay); None if it
    can't be asked (no artist, unreachable)."""
    try:
        r = requests.get(f"{RELAY_URL}/artist/status", timeout=3)
        return bool(r.json().get("recording")) if r.ok else None
    except (requests.RequestException, ValueError):
        return None


def _missed(reason):
    """A DAW recording the artist isn't capturing: say so loudly here, and
    tell the relay so the engineer app shows it. Only the streamed recording
    will exist for it — Take never starts a capture partway through, because
    the swap would then replace the whole streamed take with a partial file."""
    print(f"\n⚠  NOT CAPTURED: {daw.NAME} is recording, but the artist is not "
          f"recording this take losslessly — {reason}. Only the live-streamed "
          f"recording will be on the track. Stop and record again to capture it.\n",
          flush=True)
    try:
        requests.post(f"{RELAY_URL}/takes/missed",
                      json={"at": time.strftime("%H:%M:%S"), "reason": reason}, timeout=3)
    except requests.RequestException:
        pass


def run(stop_evt):
    """Start/stop the artist's capture with the DAW's recording. Runs from the
    moment the engineer backend starts — before the artist joins — so a
    recording started as soon as they join is already followed."""
    was_recording = None  # unknown until the first live reading
    capturing = False     # the artist confirmed it's capturing the current recording
    while not stop_evt.is_set():
        # While the DAW isn't reachable its state says nothing about the
        # transport — hold the last known state and act on the next
        # transition once it's back.
        if daw.alive():
            recording = daw.is_recording()
            if recording and not was_recording:
                if was_recording is None:
                    # Already rolling when Take started watching (e.g. the
                    # engineer backend was restarted mid-take). The artist
                    # may well be capturing it already — follow it if so.
                    if _artist_recording():
                        capturing = True
                        print(f"{daw.NAME} was already recording and the artist is "
                              f"capturing it — following that take.", flush=True)
                    else:
                        _missed(f"{daw.NAME} was already recording when Take started")
                else:
                    capturing, reason = _trigger("record")
                    if not capturing:
                        _missed(reason)
            elif was_recording and not recording:
                if capturing or _artist_recording():
                    _trigger("stop")
                else:
                    print(f"{daw.NAME} stopped recording — that take wasn't captured "
                          f"by the artist, so there's nothing to transfer.", flush=True)
                capturing = False
            was_recording = recording
        stop_evt.wait(POLL_INTERVAL)


if __name__ == "__main__":
    print(f"Following {daw.NAME}'s record state (Ctrl+C to stop)...")
    stop = threading.Event()
    try:
        run(stop)
    except KeyboardInterrupt:
        stop.set()
