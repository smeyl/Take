"""Follow the DAW's own transport: when the engineer hits Record in the DAW,
start the artist's lossless capture; when they stop, stop it.

Makes exactly the calls the engineer app's old Rec/Stop button made — the
relay's /artist/record and /artist/stop — so the artist side runs its usual
countdown, capture, stop and file transfer. Runs on the engineer's machine,
next to the DAW and the relay. DAW-agnostic: it only asks daw.py whether the
DAW is reachable and recording.
"""
import threading

import requests

import daw

RELAY_URL = "http://127.0.0.1:5010"
POLL_INTERVAL = 0.05  # seconds — same cadence as timecode.sender


def _trigger(endpoint):
    try:
        r = requests.post(f"{RELAY_URL}/artist/{endpoint}", timeout=5)
        print(f"{daw.NAME} {'started' if endpoint == 'record' else 'stopped'} "
              f"recording → artist {endpoint}: HTTP {r.status_code}", flush=True)
    except requests.RequestException as e:
        print(f"{daw.NAME} → artist {endpoint} failed: {e}", flush=True)


def run(stop_evt):
    was_recording = None  # unknown until the first live reading
    while not stop_evt.is_set():
        # While the DAW's Take-side companion isn't reporting, its state says
        # nothing about the transport — hold the last known state and act on
        # the next transition once it's back.
        if daw.alive():
            recording = daw.is_recording()
            # First reading only sets the baseline: a recording already rolling
            # when Take starts is not a new take.
            if was_recording is not None and recording != was_recording:
                _trigger("record" if recording else "stop")
            was_recording = recording
        stop_evt.wait(POLL_INTERVAL)


if __name__ == "__main__":
    print(f"Following {daw.NAME}'s record state (Ctrl+C to stop)...")
    stop = threading.Event()
    try:
        run(stop)
    except KeyboardInterrupt:
        stop.set()
