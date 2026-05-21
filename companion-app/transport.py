import logging
import os
import queue
import threading
from datetime import datetime
from flask import Flask, jsonify
from flask_cors import CORS
import sounddevice as sd
import soundfile as sf
import cue_receiver

logging.getLogger("werkzeug").setLevel(logging.ERROR)

RECORDINGS_PATH = os.path.join(os.path.dirname(__file__), "recordings")
PORT = 5004
RATE = 44100
CHANNELS = 1

app = Flask(__name__)
CORS(app)

_lock = threading.Lock()
_recording = False
_take = 0
_stream = None
_sf_file = None
_write_queue = queue.Queue()
_stop_writer = threading.Event()
_writer_thread = None


def _writer(sf_file, stop_evt):
    while not stop_evt.is_set() or not _write_queue.empty():
        try:
            data = _write_queue.get(timeout=0.1)
            sf_file.write(data)
        except queue.Empty:
            continue


@app.route("/record", methods=["POST"])
def record():
    global _recording, _take, _stream, _sf_file, _writer_thread, _stop_writer
    with _lock:
        if _recording:
            return jsonify({"error": "already recording"}), 409
        _take += 1
        os.makedirs(RECORDINGS_PATH, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(RECORDINGS_PATH, f"T{_take}_{timestamp}.wav")
        _sf_file = sf.SoundFile(path, mode="w", samplerate=RATE, channels=CHANNELS, subtype="PCM_16")
        _stop_writer = threading.Event()
        _writer_thread = threading.Thread(target=_writer, args=(_sf_file, _stop_writer), daemon=True)
        _writer_thread.start()

        def callback(indata, frames, time_info, status):
            _write_queue.put(indata.copy())

        _stream = sd.InputStream(samplerate=RATE, channels=CHANNELS, dtype="int16", callback=callback)
        _stream.start()
        _recording = True
        print(f"Recording started — T{_take}", flush=True)
        return jsonify({"recording": True, "take": _take})


@app.route("/stop", methods=["POST"])
def stop():
    global _recording, _stream, _sf_file, _writer_thread
    with _lock:
        if not _recording:
            return jsonify({"error": "not recording"}), 409
        _stream.stop()
        _stream.close()
        _stream = None
        _stop_writer.set()
        _writer_thread.join()
        _sf_file.close()
        _sf_file = None
        _recording = False
        print(f"Recording stopped — T{_take} saved", flush=True)
        return jsonify({"recording": False, "take": _take})


@app.route("/status", methods=["GET"])
def status():
    with _lock:
        return jsonify({"recording": _recording, "take": _take})


@app.route("/cue/local/<param>/<int:value>", methods=["POST"])
def cue_local(param, value):
    if param not in cue_receiver.params:
        return jsonify({"error": "unknown param"}), 400
    cue_receiver.params[param] = max(0, min(100, value))
    return jsonify({"ok": True, "param": param, "value": cue_receiver.params[param]})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
