import logging
import socket
import sys
import threading

import numpy as np
import pyaudio
from flask import Flask, request, jsonify
from flask_cors import CORS

HOST = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
UDP_PORT = 5002
FLASK_PORT = 5007
CHUNK = 1024
RATE = 44100
CHANNELS = 1
QUALITY_FILE = "/tmp/take_stream_quality"

stream_quality = "AAC256"  # "AAC128" | "AAC256" | "FLAC"

app = Flask(__name__)
CORS(app)
logging.getLogger("werkzeug").setLevel(logging.ERROR)


@app.route("/stream-quality", methods=["POST"])
def set_stream_quality():
    global stream_quality
    data = request.get_json(silent=True) or {}
    q = data.get("quality", "AAC256")
    if q not in ("AAC128", "AAC256", "FLAC"):
        return jsonify({"error": "invalid quality"}), 400
    stream_quality = q
    try:
        with open(QUALITY_FILE, "w") as fh:
            fh.write(q)
    except OSError:
        pass
    return jsonify({"ok": True, "quality": stream_quality})


def encode(raw_bytes):
    """Encode raw int16 PCM bytes at the current stream_quality."""
    samples = np.frombuffer(raw_bytes, dtype=np.int16)
    if stream_quality == "AAC128":
        return samples.tobytes()                                    # 16-bit PCM
    elif stream_quality == "AAC256":
        return (samples.astype(np.int32) << 8).tobytes()           # 24-bit packed as int32
    else:                                                           # FLAC → 32-bit float
        return (samples.astype(np.float32) / 32768.0).tobytes()


def run_flask():
    app.run(host="0.0.0.0", port=FLASK_PORT, use_reloader=False)


def run_sender(host=None):
    target = host or HOST
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    audio = pyaudio.PyAudio()
    stream = audio.open(format=pyaudio.paInt16, channels=CHANNELS, rate=RATE,
                        input=True, frames_per_buffer=CHUNK)
    print(f"Streaming microphone to {target}:{UDP_PORT}")
    try:
        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            sock.sendto(encode(data), (target, UDP_PORT))
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()
        sock.close()


if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    run_sender()
