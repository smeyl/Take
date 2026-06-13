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

stream_quality = "PCM16"  # "PCM16" | "PCM24" | "Float32"

# Names used by pre-rename UI builds — same wire formats, honest labels now.
_LEGACY_QUALITY = {"AAC128": "PCM16", "AAC256": "PCM24", "FLAC": "Float32"}

app = Flask(__name__)
CORS(app)
logging.getLogger("werkzeug").setLevel(logging.ERROR)


@app.route("/stream-quality", methods=["POST"])
def set_stream_quality():
    global stream_quality
    data = request.get_json(silent=True) or {}
    q = data.get("quality", "PCM16")
    q = _LEGACY_QUALITY.get(q, q)
    if q not in ("PCM16", "PCM24", "Float32"):
        return jsonify({"error": "invalid quality"}), 400
    stream_quality = q
    try:
        with open(QUALITY_FILE, "w") as fh:
            fh.write(q)
    except OSError:
        pass
    return jsonify({"ok": True, "quality": stream_quality})


# Wire format: 1 header byte identifying the payload encoding, then PCM data.
# Without the header the receiver would play 24-bit/float packets as int16 noise.
FMT_INT16   = b"\x00"
FMT_INT24   = b"\x01"  # 24-bit packed as int32, left-shifted 8
FMT_FLOAT32 = b"\x02"


def encode(raw_bytes):
    """Encode raw int16 PCM bytes at the current stream_quality."""
    samples = np.frombuffer(raw_bytes, dtype=np.int16)
    if stream_quality == "PCM16":
        return FMT_INT16 + samples.tobytes()
    elif stream_quality == "PCM24":
        return FMT_INT24 + (samples.astype(np.int32) << 8).tobytes()
    else:                                                           # Float32
        return FMT_FLOAT32 + (samples.astype(np.float32) / 32768.0).tobytes()


def decode_to_int16(packet):
    """Decode a stream packet back to raw int16 PCM bytes for playback."""
    if not packet:
        return b""
    fmt, payload = packet[:1], packet[1:]
    if fmt == FMT_INT24:
        return (np.frombuffer(payload, dtype=np.int32) >> 8).astype(np.int16).tobytes()
    if fmt == FMT_FLOAT32:
        samples = np.clip(np.frombuffer(payload, dtype=np.float32), -1.0, 1.0)
        return (samples * 32767.0).astype(np.int16).tobytes()
    return payload  # FMT_INT16


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
