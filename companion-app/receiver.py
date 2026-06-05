import logging
import os
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

INCOMING_PATH = os.path.join(os.path.dirname(__file__), "incoming")
PORT = 5001
SYNC_FORMAT_FILE = "/tmp/take_sync_format"

on_file_received = None  # optional callback(filename, size) set by the host app
sync_format = "WAV24"    # "WAV24" | "WAV32f" | "FLAC"
_received_takes = []

app = Flask(__name__)
CORS(app)
logging.getLogger("werkzeug").setLevel(logging.ERROR)


@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return "No file in request", 400
    f = request.files["file"]
    if not f.filename:
        return "Empty filename", 400
    os.makedirs(INCOMING_PATH, exist_ok=True)
    dest = os.path.join(INCOMING_PATH, f.filename)
    f.save(dest)
    size = os.path.getsize(dest)
    _received_takes.append({"name": f.filename, "size": size, "time": datetime.now().isoformat()})
    print(f"Received: {f.filename} ({size} bytes)")
    if on_file_received:
        on_file_received(f.filename, size)
    return "OK", 200


@app.route("/takes", methods=["GET"])
def get_takes():
    return jsonify(_received_takes)


@app.route("/sync-format", methods=["POST"])
def set_sync_format():
    global sync_format
    data = request.get_json(silent=True) or {}
    fmt = data.get("format", "WAV24")
    if fmt not in ("WAV24", "WAV32f", "FLAC"):
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
