import json
import logging
import os
import threading
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

# Data lives at the repo root (sibling of this backend/ folder), not inside it.
INCOMING_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "incoming")
PORT = 5001         # engineer's receiver: takes uploaded by the artist
ARTIST_PORT = 5009  # artist's receiver: backing track bounced by the engineer
SYNC_FORMAT_FILE = "/tmp/take_sync_format"
TRACKS_FILE = "/tmp/take_tracks.json"

on_file_received = None  # optional callback(filename, size) set by the host app
sync_format = "WAV24"    # "FLAC" | "WAV24" | "WAV32f"  (compressed → raw)
_received_takes = []
_takes_lock = threading.Lock()


def update_take_status(filename, status):
    """Thread-safe status update called by engineer.py after swap/insert."""
    with _takes_lock:
        for t in _received_takes:
            if t["name"] == filename:
                t["status"] = status
                return

app = Flask(__name__)
CORS(app)
logging.getLogger("werkzeug").setLevel(logging.ERROR)


@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return "No file in request", 400
    f = request.files["file"]
    # basename() strips any path components so an upload can't escape INCOMING_PATH
    filename = os.path.basename(f.filename or "")
    if not filename:
        return "Empty filename", 400
    os.makedirs(INCOMING_PATH, exist_ok=True)
    dest = os.path.join(INCOMING_PATH, filename)
    f.save(dest)
    size = os.path.getsize(dest)
    with _takes_lock:
        _received_takes.append({
            "name": filename,
            "size": size,
            "time": datetime.now().isoformat(),
            "status": "syncing",
        })
    print(f"Received: {filename} ({size} bytes)")
    if on_file_received:
        on_file_received(filename, size)
    return "OK", 200


@app.route("/takes", methods=["GET"])
def get_takes():
    with _takes_lock:
        return jsonify(list(_received_takes))


@app.route("/tracks", methods=["GET"])
def get_tracks():
    """Reaper track list, kept current by take_session.lua."""
    try:
        with open(TRACKS_FILE) as fh:
            return jsonify(json.load(fh))
    except (OSError, ValueError):
        return jsonify([])


@app.route("/sync-format", methods=["POST"])
def set_sync_format():
    global sync_format
    data = request.get_json(silent=True) or {}
    fmt = data.get("format", "WAV24")
    if fmt not in ("FLAC", "WAV24", "WAV32f"):
        return jsonify({"error": "invalid format"}), 400
    sync_format = fmt
    try:
        with open(SYNC_FORMAT_FILE, "w") as fh:
            fh.write(fmt)
    except OSError:
        pass
    return jsonify({"ok": True, "format": sync_format})


if __name__ == "__main__":
    os.makedirs(INCOMING_PATH, exist_ok=True)
    print(f"Receiver listening on port {PORT}, saving to {INCOMING_PATH}/")
    app.run(host="0.0.0.0", port=PORT)
