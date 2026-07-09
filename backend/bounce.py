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
# Where Reaper writes the render. Set the project's render output to this path
# (MP3, stereo) once — see the README Reaper setup. take_session.lua triggers
# the render via ReaScript (the web API render action 404s on this setup).
RENDER_OUTPUT = "/tmp/take_backing_track.mp3"

POLL_INTERVAL = 0.5  # seconds between checks
STABLE_READS  = 3    # consecutive identical sizes = file fully written
TIMEOUT       = 120  # seconds before giving up


def wait_for_bounce():
    """Wait for take_session.lua to signal the render finished, then confirm the
    output file is present and its size has settled. Bounded by TIMEOUT so a
    missing Reaper / Take script can never wedge the bounce. Returns True on a
    complete render, False on timeout or missing output."""
    deadline = time.time() + TIMEOUT

    # 1) Wait for the Lua completion signal — proof the render action actually
    #    ran (vs. the command sitting unread because the script isn't running).
    while time.time() < deadline and not reaper.bounce_signalled():
        time.sleep(POLL_INTERVAL)
    if not reaper.bounce_signalled():
        print(f"Bounce: no completion signal from take_session.lua within "
              f"{TIMEOUT}s — is Reaper running with the Take script?")
        return False

    # 2) Confirm the rendered file exists and has stopped growing. The render
    #    action blocks until done, so this normally settles immediately; the
    #    stability check just guards a slow flush.
    last_size, stable = -1, 0
    while time.time() < deadline:
        if os.path.exists(RENDER_OUTPUT):
            size = os.path.getsize(RENDER_OUTPUT)
            if size > 0 and size == last_size:
                stable += 1
                if stable >= STABLE_READS:
                    return True
            else:
                last_size, stable = size, 0
        time.sleep(POLL_INTERVAL)

    print(f"Bounce: signalled done but {RENDER_OUTPUT} never appeared/settled — "
          f"check the project's render output path and format in Reaper (README).")
    return False


bounce_app = Flask("bounce_server")
CORS(bounce_app)
logging.getLogger("werkzeug").setLevel(logging.ERROR)

_bouncing = False
_last_result = None
_last_time = None
selected_tracks = []  # empty = all tracks; list of ints = only those tracks


def _apply_track_selection():
    """Mute tracks not in selected_tracks. Returns saved (index, was_muted) pairs."""
    if not selected_tracks:
        return []
    count = reaper.get_track_count()
    saved = []
    for i in range(count):
        was_muted = reaper.get_track_muted(i)
        saved.append((i, was_muted))
        if i not in selected_tracks and not was_muted:
            reaper.set_track_muted(i, True)
    return saved


def _restore_track_selection(saved):
    for i, was_muted in saved:
        if i not in selected_tracks and not was_muted:
            reaper.set_track_muted(i, False)


def _do_bounce():
    global _bouncing, _last_result, _last_time
    saved_mutes = []
    try:
        if os.path.exists(RENDER_OUTPUT):
            os.remove(RENDER_OUTPUT)
        saved_mutes = _apply_track_selection()
        reaper.start_bounce()          # take_session.lua renders + signals done
        ok = wait_for_bounce()
        if ok:
            # Artist's file receiver — distinct port so it can never collide
            # with the engineer's take receiver in single-machine dev
            send_file(RENDER_OUTPUT, TARGET_IP, ARTIST_PORT)
            _last_result = "ok"
        else:
            _last_result = "error"
    except Exception as e:
        print(f"Bounce failed: {e}")
        _last_result = "error"
    finally:
        # Restore mutes and always clear the flag — a crash or timeout mid-bounce
        # must never leave tracks muted or lock out future bounces.
        _restore_track_selection(saved_mutes)
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
    return jsonify({"bouncing": _bouncing, "result": _last_result, "time": _last_time})


def run_bounce_server():
    bounce_app.run(host="0.0.0.0", port=BOUNCE_PORT)


if __name__ == "__main__":
    if os.path.exists(RENDER_OUTPUT):
        os.remove(RENDER_OUTPUT)

    print("Bouncing project in Reaper (via take_session.lua)...")
    reaper.start_bounce()

    print(f"Waiting for render → {RENDER_OUTPUT}")
    if not wait_for_bounce():
        print(f"ERROR: Render did not complete within {TIMEOUT}s.")
        raise SystemExit(1)

    print("Render complete. Sending to artist...")
    send_file(RENDER_OUTPUT, TARGET_IP, ARTIST_PORT)
    print("Backing track sent to artist")
