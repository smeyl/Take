import logging
import os
import threading
import time
from datetime import datetime

import requests
from flask import Flask, jsonify
from flask_cors import CORS

from reaper import BASE
from sender import send_file

TARGET_IP = "127.0.0.1"  # set by start_engineer.py after artist joins
BOUNCE_PORT = 5006
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


bounce_app = Flask("bounce_server")
CORS(bounce_app)
logging.getLogger("werkzeug").setLevel(logging.ERROR)

_bouncing = False
_last_result = None
_last_time = None


def _do_bounce():
    global _bouncing, _last_result, _last_time
    if os.path.exists(RENDER_OUTPUT):
        os.remove(RENDER_OUTPUT)
    ok = trigger_render() and wait_for_render(RENDER_OUTPUT)
    if ok:
        send_file(RENDER_OUTPUT, TARGET_IP)
        _last_result = "ok"
    else:
        _last_result = "error"
    _last_time = datetime.now().isoformat()
    _bouncing = False


@bounce_app.route("/bounce", methods=["POST"])
def bounce_route():
    global _bouncing
    if _bouncing:
        return jsonify({"error": "already bouncing"}), 409
    _bouncing = True
    threading.Thread(target=_do_bounce, daemon=True).start()
    return jsonify({"ok": True})


@bounce_app.route("/bounce/status", methods=["GET"])
def bounce_status():
    return jsonify({"bouncing": _bouncing, "result": _last_result, "time": _last_time})


def run_bounce_server():
    bounce_app.run(host="0.0.0.0", port=BOUNCE_PORT)


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
