import os
import logging
import threading
import time
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

def _is_auto_sync_enabled():
    try:
        r = requests.get(f"{RELAY_URL}/auto-sync", timeout=2)
        return r.ok and r.json().get("enabled", True)
    except requests.RequestException:
        return True  # default to enabled if relay unreachable


def _insert_media_flow(filename, force=False):
    filepath = os.path.join(INCOMING_PATH, filename)
    print(f"[sync] {filename}: placing in Reaper (force={force})")

    if not force and not _is_auto_sync_enabled():
        take_label = filename.split("_")[0] if "_" in filename else filename
        print(f"[sync] auto-sync disabled — skipping swap for {take_label}")
        return

    # Try file swap: replace the BlackHole-recorded stream item with the lossless file.
    # Requires take_session.lua running in Reaper and a prior recording in this session.
    try:
        # Swap info left over from a crashed/killed session must not place a
        # new take at an old position — treat anything older than an hour as gone.
        age = time.time() - os.path.getmtime(reaper.START_FILE)
        if age > 3600:
            os.remove(reaper.START_FILE)
            print(f"[sync] discarding stale swap info ({age:.0f}s old) — "
                  f"falling back to insert")
            raise FileNotFoundError(reaper.START_FILE)
        with open(reaper.START_FILE) as f:
            lines = f.read().strip().split("\n")
        start_time = float(lines[0])
        track_idx  = int(lines[1]) if len(lines) > 1 else 0
        print(f"[sync] swap info: track {track_idx}, position {start_time:.3f}s "
              f"(from {reaper.START_FILE})")
        # Atomic write via reaper._write_cmd — never a partial read in Lua
        reaper._write_cmd(["swap", filepath, track_idx, f"{start_time:.6f}"])
        # Consume the start info so a later, unrelated file can't swap onto
        # this take's position — it falls through to a plain insert instead.
        os.remove(reaper.START_FILE)
        receiver.update_take_status(filename, "done")
        print(f"[sync] swap queued for take_session.lua — {filename}")
        return
    except FileNotFoundError:
        print(f"[sync] no swap info ({reaper.START_FILE} missing — no recording "
              f"this session, or already consumed) — falling back to insert")
    except Exception as e:
        print(f"[sync] swap failed ({e}) — falling back to insert")

    # Fallback: insert as a new item on the selected destination track (used
    # before the first recording of a session, or if take_session.lua is not running)
    try:
        track = _get_selected_track()
        action = _insert_action_id()
        print(f"[sync] insert via Reaper action {action} (track {track})")
        with open(TEMP_FILE, "w") as f:
            f.write(filepath + "\n" + str(track))
        r = requests.get(f"{BASE}/_/{action}", timeout=5)
        if not r.ok:
            print(f"[sync] Reaper web API returned HTTP {r.status_code} — "
                  f"is the action ID stale? ({INSERT_ID_FILE})")
        receiver.update_take_status(filename, "done")
        print(f"[sync] placed {filename} on track {track}")
    except requests.RequestException as e:
        print(f"[sync] Reaper unreachable — could not place {filename} ({e})")


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
    print(f"  Insert action : {_insert_action_id()}")

    try:
        while True:
            threading.Event().wait(timeout=1)
    except KeyboardInterrupt:
        print("\nShutting down.")
