import logging
import os
import threading
import time
from datetime import datetime

from flask import Flask, jsonify, request
from flask_cors import CORS

import daw
from receiver import ARTIST_PORT
from sender import send_file

TARGET_IP = "127.0.0.1"  # set by start_engineer.py after artist joins
BOUNCE_PORT = 5006
# The DAW renders each bounce to its own file (daw.bounce_output_path(); a
# fresh name each time, so no overwrite prompt). The artist side watches a
# fixed path, so we send under this name:
ARTIST_FILENAME = "take_backing_track.mp3"  # = backing_player.BACKING_PATH

POLL_INTERVAL = 0.5  # seconds between checks
STABLE_READS  = 3    # consecutive identical sizes = file fully written
TIMEOUT       = 120  # seconds before giving up


def wait_for_bounce():
    """Wait for the DAW to signal the render finished, then confirm the output
    file is present and its size has settled. Bounded by TIMEOUT so a DAW that
    isn't running or never finishes can't wedge the bounce. Returns the
    rendered file's path on a complete render, None on timeout/missing output."""
    deadline = time.time() + TIMEOUT

    # 1) Wait for the DAW's completion signal — proof the render actually ran.
    while time.time() < deadline and not daw.bounce_signalled():
        time.sleep(POLL_INTERVAL)
    if not daw.bounce_signalled():
        print(f"Bounce: {daw.NAME} didn't finish the export within {TIMEOUT}s — "
              f"is {daw.NAME} running with a session open?")
        return None

    # The signal file names the actual render output for this bounce.
    output = daw.bounce_output_path()
    if not output:
        print(f"Bounce: {daw.NAME}'s export failed — see the error above; nothing "
              f"was sent to the artist.")
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

    print(f"Bounce: {daw.NAME} reported the export done, but {output} never "
          f"appeared or finished writing.")
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
        daw.start_bounce(selected_tracks)
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
    print(f"Bouncing the {daw.NAME} session...")
    daw.start_bounce()

    print("Waiting for render...")
    rendered = wait_for_bounce()
    if not rendered:
        print(f"ERROR: Render did not complete within {TIMEOUT}s.")
        raise SystemExit(1)

    print(f"Render complete ({rendered}). Sending to artist...")
    if send_file(rendered, TARGET_IP, ARTIST_PORT, filename=ARTIST_FILENAME):
        os.remove(rendered)
        print("Backing track sent to artist")
