import os
from flask import Flask, request
from flask_cors import CORS

INCOMING_PATH = os.path.join(os.path.dirname(__file__), "incoming")
PORT = 5001

on_file_received = None  # optional callback(filename, size) set by the host app

app = Flask(__name__)
CORS(app)


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
    print(f"Received: {f.filename} ({size} bytes)")
    if on_file_received:
        on_file_received(f.filename, size)
    return "OK", 200


if __name__ == "__main__":
    os.makedirs(INCOMING_PATH, exist_ok=True)
    print(f"Receiver listening on port {PORT}, saving to {INCOMING_PATH}/")
    app.run(host="0.0.0.0", port=PORT)
