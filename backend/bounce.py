import logging
import os
import threading
import time
from datetime import datetime

from flask import Flask, jsonify, request
from flask_cors import CORS

import reaper
from receiver import ARTIST_PORT
from sender import send_file

TARGET_IP = "127.0.0.1"  # set by start_engineer.py after artist joins
BOUNCE_PORT = 5006
# take_session.lua renders each bounce to a unique /tmp/session_BT_<ts>.mp3 (so
# Reaper never raises an overwrite prompt) and reports the path in its done
# signal. The artist side watches a fixed path, so we send under this name:
ARTIST_FILENAME = "take_backing_track.mp3"  # = backing_player.BACKING_PATH

POLL_INTERVAL = 0.5  # seconds between checks
STABLE_READS  = 3    # consecutive identical sizes = file fully written
TIMEOUT       = 120  # seconds before giving up


def wait_for_bounce():
    """Wait for take_session.lua to signal the render finished, then confirm the
    output file is present and its size has settled. Bounded by TIMEOUT so a
    missing Reaper / Take script can never wedge the bounce. Returns the
    rendered file's path on a complete render, None on timeout/missing output."""
    deadline = time.time() + TIMEOUT

    # 1) Wait for the Lua completion signal — proof the render action actually
    #    ran (vs. the command sitting unread because the script isn't running).
    while time.time() < deadline and not reaper.bounce_signalled():
        time.sleep(POLL_INTERVAL)
    if not reaper.bounce_signalled():
        print(f"Bounce: no completion signal from take_session.lua within "
              f"{TIMEOUT}s — is Reaper running with the Take script?")
        return None

    # The signal file names the actual render output for this bounce.
    output = reaper.bounce_output_path()
    if not output:
        print("Bounce: done signal contained no output path — is take_session.lua "
              "up to date? (restart Reaper after updating the Take scripts)")
        return None

    # 2) Confirm the rendered file exists and has stopped growing. The render
    #    action blocks until done, so this normally settles immediately; the
    #    stability check just guards a slow flush.
    last_size, stable = -1, 0
    while time.time() < deadline:
        if os.path.exists(output):
            size = os.path.getsize(output)
            if size > 0 and size == last_size:
                stable += 1
                if stable >= STABLE_READS:
                    return output
            else:
                last_size, stable = size, 0
        time.sleep(POLL_INTERVAL)

    print(f"Bounce: signalled done but {output} never appeared/settled — "
          f"check the Reaper console for render errors.")
    return None


bounce_app = Flask("bounce_server")
CORS(bounce_app)
logging.getLogger("werkzeug").setLevel(logging.ERROR)

_bouncing = False
_last_result = None
_last_time = None
_last_file = None  # basename of the last successful render, shown in the UI
selected_tracks = []  # empty = all tracks; list of ints = only those tracks


def _do_bounce():
    global _bouncing, _last_result, _last_time, _last_file
    try:
        # take_session.lua mutes the unselected tracks around the render and
        # restores them — no web API involved (it 404s on this setup).
        reaper.start_bounce(selected_tracks)
        rendered = wait_for_bounce()
        if rendered:
            # Artist's file receiver — distinct port so it can never collide
            # with the engineer's take receiver in single-machine dev. Sent
            # under the fixed name the artist's backing player watches for.
            if send_file(rendered, TARGET_IP, ARTIST_PORT,
                         filename=ARTIST_FILENAME):
                _last_result = "ok"
                _last_file = os.path.basename(rendered)
                os.remove(rendered)  # unique per bounce — don't pile up in /tmp
            else:
                _last_result = "error"
        else:
            _last_result = "error"
    except Exception as e:
        print(f"Bounce failed: {e}")
        _last_result = "error"
    finally:
        # Always clear the flag — a crash or timeout mid-bounce must never
        # lock out future bounces.
        _last_time = datetime.now().isoformat()
        _bouncing = False


@bounce_app.route("/bounce/tracks", methods=["POST"])
def set_bounce_tracks():
    global selected_tracks
    data = request.get_json(force=True, silent=True) or {}
    selected_tracks = [int(i) for i in data.get("tracks", [])]
    return jsonify({"ok": True, "selected_tracks": selected_tracks})


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
    return jsonify({"bouncing": _bouncing, "result": _last_result,
                    "time": _last_time, "file": _last_file})


def run_bounce_server():
    bounce_app.run(host="0.0.0.0", port=BOUNCE_PORT)


if __name__ == "__main__":
    print("Bouncing project in Reaper (via take_session.lua)...")
    reaper.start_bounce()

    print("Waiting for render...")
    rendered = wait_for_bounce()
    if not rendered:
        print(f"ERROR: Render did not complete within {TIMEOUT}s.")
        raise SystemExit(1)

    print(f"Render complete ({rendered}). Sending to artist...")
    if send_file(rendered, TARGET_IP, ARTIST_PORT, filename=ARTIST_FILENAME):
        os.remove(rendered)
        print("Backing track sent to artist")
