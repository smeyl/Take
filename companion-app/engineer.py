import os
import logging
import threading
import requests
from flask import jsonify, request as flask_request

import receiver
import reaper
from receiver import app, INCOMING_PATH, PORT
from reaper import BASE

ACTION_INSERT_MEDIA = "_RSb5c2380eebd5068bc425e17e9f920644a2f49be8"
TEMP_FILE = "/tmp/take_incoming.txt"
RELAY_URL = "http://127.0.0.1:5010"

selected_track = 0


@app.route("/tracks", methods=["GET"])
def get_tracks_route():
    return jsonify(reaper.get_tracks())


@app.route("/track/select/<int:index>", methods=["POST"])
def select_track_route(index):
    global selected_track
    selected_track = index
    try:
        with open("/tmp/take_dest_track", "w") as f:
            f.write(str(index))
    except OSError:
        pass
    return jsonify({"ok": True, "selected_track": selected_track})


def _is_auto_sync_enabled():
    try:
        r = requests.get(f"{RELAY_URL}/auto-sync", timeout=2)
        return r.ok and r.json().get("enabled", True)
    except requests.RequestException:
        return True  # default to enabled if relay unreachable


def _insert_media_flow(filename):
    filepath = os.path.join(INCOMING_PATH, filename)

    if not _is_auto_sync_enabled():
        take_label = filename.split("_")[0] if "_" in filename else filename
        print(f"Auto-sync disabled — skipping swap for {take_label}")
        return

    # Try file swap: replace the BlackHole-recorded stream item with the lossless file.
    # Requires take_reaper_poll.lua running in Reaper and a prior recording in this session.
    try:
        with open(reaper.START_FILE) as f:
            lines = f.read().strip().split("\n")
        start_time = float(lines[0])
        track_idx  = int(lines[1]) if len(lines) > 1 else selected_track
        with open(reaper.CMD_FILE, "w") as f:
            f.write(f"swap\n{filepath}\n{track_idx}\n{start_time:.6f}\n")
        # Consume the start info so a later, unrelated file can't swap onto
        # this take's position — it falls through to a plain insert instead.
        os.remove(reaper.START_FILE)
        print(f"Reaper: swap queued — {filename} → track {track_idx} at {start_time:.3f}s")
        return
    except Exception as e:
        print(f"[swap] no record info available, falling back to insert ({e})")

    # Fallback: insert as a new item (used before first recording or if Lua poll script not running)
    try:
        contents = filepath + "\n" + str(selected_track)
        print(f"[insert_media] {TEMP_FILE}:\n  line1: {filepath}\n  line2: {selected_track}")
        with open(TEMP_FILE, "w") as f:
            f.write(contents)
        requests.get(f"{BASE}/_/{ACTION_INSERT_MEDIA}", timeout=5)
        print(f"Reaper: placed {filename} on timeline (track {selected_track})")
    except requests.RequestException as e:
        print(f"Reaper: request failed — could not place {filename} ({e})")


def _on_file_received(filename, size):
    threading.Thread(target=_insert_media_flow, args=(filename,), daemon=True).start()


receiver.on_file_received = _on_file_received


def run_receiver():
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    os.makedirs(INCOMING_PATH, exist_ok=True)
    app.run(host="0.0.0.0", port=PORT, use_reloader=False)


if __name__ == "__main__":
    threading.Thread(target=run_receiver, name="receiver", daemon=True).start()

    print("Take — engineer ready")
    print(f"  File receiver : 0.0.0.0:{PORT} → {INCOMING_PATH}/")
    print(f"  Reaper        : {ACTION_INSERT_MEDIA}")

    try:
        while True:
            threading.Event().wait(timeout=1)
    except KeyboardInterrupt:
        print("\nShutting down.")
