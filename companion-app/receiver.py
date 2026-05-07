import os
from flask import Flask, request

INCOMING_PATH = os.path.join(os.path.dirname(__file__), "incoming")
PORT = 5001

app = Flask(__name__)


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
    return "OK", 200


if __name__ == "__main__":
    os.makedirs(INCOMING_PATH, exist_ok=True)
    print(f"Receiver listening on port {PORT}, saving to {INCOMING_PATH}/")
    app.run(host="0.0.0.0", port=PORT)
