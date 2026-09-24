import os
import logging
import threading
import requests
from flask import jsonify

import daw
import receiver
from receiver import app, INCOMING_PATH, PORT

RELAY_URL = "http://127.0.0.1:5010"
DEST_TRACK_FILE = "/tmp/take_dest_track"


def _get_selected_track():
    try:
        with open(DEST_TRACK_FILE) as fh:
            return int(fh.read().strip())
    except (OSError, ValueError):
        return 0

def _is_auto_sync_enabled():
    try:
        r = requests.get(f"{RELAY_URL}/auto-sync", timeout=2)
        return r.ok and r.json().get("enabled", True)
    except requests.RequestException:
        return True  # default to enabled if relay unreachable


def _insert_media_flow(filename, force=False):
    filepath = os.path.join(INCOMING_PATH, filename)
    print(f"[sync] {filename}: placing in {daw.NAME} (force={force})")

    if not force and not _is_auto_sync_enabled():
        take_label = filename.split("_")[0] if "_" in filename else filename
        print(f"[sync] auto-sync disabled — skipping swap for {take_label}")
        return

    result = daw.place_take(filepath, _get_selected_track())
    if result == "not_running":
        print(f"[sync] {filename} saved to {INCOMING_PATH}/ but not placed in {daw.NAME}")
        return
    receiver.update_take_status(filename, "done")


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
    try:
        app.run(host="0.0.0.0", port=PORT, use_reloader=False)
    except OSError:
        # Without this receiver, takes can't arrive and swaps can't run.
        # Don't let that fail silently in a background thread.
        print(f"FATAL: file receiver could not bind port {PORT} — another "
              f"process owns it (lsof -i :{PORT}). Takes will NOT sync.",
              flush=True)


if __name__ == "__main__":
    threading.Thread(target=run_receiver, name="receiver", daemon=True).start()

    print("Take — engineer ready")
    print(f"  File receiver : 0.0.0.0:{PORT} → {INCOMING_PATH}/")

    try:
        while True:
            threading.Event().wait(timeout=1)
    except KeyboardInterrupt:
        print("\nShutting down.")
