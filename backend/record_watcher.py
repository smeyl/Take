"""Follow Reaper's own transport: when the engineer hits Record in Reaper, start
the artist's lossless capture; when they stop, stop it.

Makes exactly the calls the engineer app's old Rec/Stop button made — the
relay's /artist/record and /artist/stop — so the artist side runs its usual
countdown, capture, stop and file transfer. Runs on the engineer's machine,
next to Reaper and the relay.
"""
import threading

import requests

import reaper

RELAY_URL = "http://127.0.0.1:5010"
POLL_INTERVAL = 0.05  # seconds — same cadence as timecode.sender


def _trigger(endpoint):
    try:
        r = requests.post(f"{RELAY_URL}/artist/{endpoint}", timeout=5)
        print(f"Reaper {'started' if endpoint == 'record' else 'stopped'} "
              f"recording → artist {endpoint}: HTTP {r.status_code}", flush=True)
    except requests.RequestException as e:
        print(f"Reaper → artist {endpoint} failed: {e}", flush=True)


def run(stop_evt):
    was_recording = None  # unknown until the first live reading
    while not stop_evt.is_set():
        # A stale export (Reaper or take_session.lua gone) says nothing about
        # the transport — hold the last known state and act on the next
        # transition once the script is back.
        if reaper.script_alive():
            recording = reaper.is_recording()
            # First reading only sets the baseline: a recording already rolling
            # when Take starts is not a new take.
            if was_recording is not None and recording != was_recording:
                _trigger("record" if recording else "stop")
            was_recording = recording
        stop_evt.wait(POLL_INTERVAL)


if __name__ == "__main__":
    print("Following Reaper's record state (Ctrl+C to stop)...")
    stop = threading.Event()
    try:
        run(stop)
    except KeyboardInterrupt:
        stop.set()
