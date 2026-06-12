import os
import logging
import threading
import requests
from flask import jsonify

import receiver
import reaper
from receiver import app, INCOMING_PATH, PORT
from reaper import BASE

TEMP_FILE = "/tmp/take_incoming.txt"
RELAY_URL = "http://127.0.0.1:5010"
INSERT_ID_FILE = "/tmp/take_insert_cmd_id"
DEST_TRACK_FILE = "/tmp/take_dest_track"

# Fallback for setups predating auto-registration (take_session.lua writes the
# real ID to INSERT_ID_FILE on every Reaper launch).
_INSERT_ACTION_FALLBACK = "_RSb5c2380eebd5068bc425e17e9f920644a2f49be8"


def _insert_action_id():
    try:
        with open(INSERT_ID_FILE) as fh:
            action = fh.read().strip()
            if action:
                return action
    except OSError:
        pass
    return _INSERT_ACTION_FALLBACK


def _get_selected_track():
    try:
        with open(DEST_TRACK_FILE) as fh:
            return int(fh.read().strip())
    except (OSError, ValueError):
        return 0

@app.route("/tracks", methods=["GET"])
def get_tracks_route():
    return jsonify(reaper.get_tracks())


def _is_auto_sync_enabled():
    try:
        r = requests.get(f"{RELAY_URL}/auto-sync", timeout=2)
        return r.ok and r.json().get("enabled", True)
    except requests.RequestException:
        return True  # default to enabled if relay unreachable


def _insert_media_flow(filename, force=False):
    filepath = os.path.join(INCOMING_PATH, filename)

    if not force and not _is_auto_sync_enabled():
        take_label = filename.split("_")[0] if "_" in filename else filename
        print(f"Auto-sync disabled — skipping swap for {take_label}")
        return

    # Try file swap: replace the BlackHole-recorded stream item with the lossless file.
    # Requires take_session.lua running in Reaper and a prior recording in this session.
    try:
        with open(reaper.START_FILE) as f:
            lines = f.read().strip().split("\n")
        start_time = float(lines[0])
        track_idx  = int(lines[1]) if len(lines) > 1 else 0
        with open(reaper.CMD_FILE, "w") as f:
            f.write(f"swap\n{filepath}\n{track_idx}\n{start_time:.6f}\n")
        # Consume the start info so a later, unrelated file can't swap onto
        # this take's position — it falls through to a plain insert instead.
        os.remove(reaper.START_FILE)
        receiver.update_take_status(filename, "done")
        print(f"Reaper: swap queued — {filename} → track {track_idx} at {start_time:.3f}s")
        return
    except Exception:
        pass  # no record info from this session — insert as a new item instead

    # Fallback: insert as a new item on the selected destination track (used
    # before the first recording of a session, or if take_session.lua is not running)
    try:
        track = _get_selected_track()
        with open(TEMP_FILE, "w") as f:
            f.write(filepath + "\n" + str(track))
        requests.get(f"{BASE}/_/{_insert_action_id()}", timeout=5)
        receiver.update_take_status(filename, "done")
        print(f"Reaper: placed {filename} on track {track}")
    except requests.RequestException as e:
        print(f"Reaper: request failed — could not place {filename} ({e})")


@app.route("/takes/<path:filename>/swap", methods=["POST"])
def manual_swap(filename):
    """Engineer-triggered swap for takes skipped while auto-sync was off."""
    filename = os.path.basename(filename)
    filepath = os.path.join(INCOMING_PATH, filename)
    if not os.path.isfile(filepath):
        return jsonify({"error": "file not found"}), 404
    threading.Thread(target=_insert_media_flow, args=(filename, True), daemon=True).start()
    return jsonify({"ok": True, "file": filename})


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
    print(f"  Insert action : {_insert_action_id()}")

    try:
        while True:
            threading.Event().wait(timeout=1)
    except KeyboardInterrupt:
        print("\nShutting down.")
