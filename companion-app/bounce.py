import os
import time
import requests

from reaper import BASE
from sender import send_file

TARGET_IP = "127.0.0.1"  # change this for real network testing
RENDER_OUTPUT = "/tmp/take_backing_track.mp3"

# File: Render project, using most recent render settings, auto-close render dialog
# Pre-requisite: run File > Render once in Reaper, set output to RENDER_OUTPUT,
# format to MP3 stereo, then save. Action 42230 will reuse those settings.
ACTION_RENDER = 42230

POLL_INTERVAL = 1.0  # seconds between size checks
STABLE_READS  = 3    # consecutive identical sizes = render done
TIMEOUT       = 120  # seconds before giving up


def trigger_render():
    try:
        r = requests.get(f"{BASE}/_/{ACTION_RENDER}", timeout=10)
        return r.status_code == 200
    except requests.ConnectionError:
        print("ERROR: Could not connect to Reaper — is it running?")
        return False


def wait_for_render(path):
    elapsed = 0
    last_size = -1
    stable = 0

    while elapsed < TIMEOUT:
        if os.path.exists(path):
            size = os.path.getsize(path)
            if size > 0 and size == last_size:
                stable += 1
                if stable >= STABLE_READS:
                    return True
            else:
                stable = 0
                last_size = size
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

    return False


if __name__ == "__main__":
    if os.path.exists(RENDER_OUTPUT):
        os.remove(RENDER_OUTPUT)

    print("Bouncing project in Reaper...")
    if not trigger_render():
        raise SystemExit(1)

    print(f"Waiting for render → {RENDER_OUTPUT}")
    if not wait_for_render(RENDER_OUTPUT):
        print(f"ERROR: Render did not complete within {TIMEOUT}s.")
        raise SystemExit(1)

    print("Render complete. Sending to artist...")
    send_file(RENDER_OUTPUT, TARGET_IP)
    print("Backing track sent to artist")
