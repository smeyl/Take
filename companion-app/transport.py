import logging
import math
import os
import queue
import threading
from datetime import datetime
from flask import Flask, jsonify
from flask_cors import CORS
import numpy as np
import pyaudio
import soundfile as sf
import cue_receiver

logging.getLogger("werkzeug").setLevel(logging.ERROR)

RECORDINGS_PATH = os.path.join(os.path.dirname(__file__), "recordings")
PORT = 5004
RATE = 44100
CHANNELS = 1

app = Flask(__name__)
CORS(app)

levels = {"l": -60.0, "r": -60.0}

_lock = threading.Lock()
_recording = False
_take = 0
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


def _audio_thread():
    """Single PyAudio input stream: updates levels always, feeds recorder when active."""
    CHUNK = 1024
    pa = pyaudio.PyAudio()
    stream = None
    for ch in (2, 1):
        try:
            stream = pa.open(format=pyaudio.paInt16, channels=ch,
                             rate=RATE, input=True, frames_per_buffer=CHUNK)
            break
        except Exception:
            continue
    if stream is None:
        pa.terminate()
        return

    while True:
        try:
            raw = stream.read(CHUNK, exception_on_overflow=False)
        except OSError:
            break

        # Meter — always running
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        if ch >= 2:
            lr = samples.reshape(-1, 2)
            l_rms = float(np.sqrt(np.mean(lr[:, 0] ** 2)))
            r_rms = float(np.sqrt(np.mean(lr[:, 1] ** 2)))
        else:
            l_rms = r_rms = float(np.sqrt(np.mean(samples ** 2)))
        levels["l"] = max(-60.0, min(0.0, 20.0 * math.log10(l_rms + 1e-9)))
        levels["r"] = max(-60.0, min(0.0, 20.0 * math.log10(r_rms + 1e-9)))

        # Recording feed — only when active
        if _recording:
            chunk = np.frombuffer(raw, dtype=np.int16)
            if ch > CHANNELS:
                # downmix stereo → mono by averaging
                chunk = chunk.reshape(-1, ch).mean(axis=1).astype(np.int16)
            _write_queue.put(chunk.reshape(-1, CHANNELS).copy())

    stream.stop_stream()
    stream.close()
    pa.terminate()


threading.Thread(target=_audio_thread, daemon=True).start()


@app.route("/record", methods=["POST"])
def record():
    global _recording, _take, _sf_file, _writer_thread, _stop_writer
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
        _recording = True
        print(f"Recording started — T{_take}", flush=True)
        return jsonify({"recording": True, "take": _take})


@app.route("/stop", methods=["POST"])
def stop():
    global _recording, _sf_file, _writer_thread
    with _lock:
        if not _recording:
            return jsonify({"error": "not recording"}), 409
        _recording = False       # audio thread stops feeding the queue
        _stop_writer.set()
        _writer_thread.join()    # drain any buffered chunks before closing
        _sf_file.close()
        _sf_file = None
        print(f"Recording stopped — T{_take} saved", flush=True)
        return jsonify({"recording": False, "take": _take})


@app.route("/status", methods=["GET"])
def status():
    with _lock:
        return jsonify({"recording": _recording, "take": _take})


@app.route("/levels", methods=["GET"])
def get_levels():
    return jsonify(levels)


@app.route("/cue/local/<param>/<int:value>", methods=["POST"])
def cue_local(param, value):
    if param not in cue_receiver.params:
        return jsonify({"error": "unknown param"}), 400
    cue_receiver.params[param] = max(0, min(100, value))
    return jsonify({"ok": True, "param": param, "value": cue_receiver.params[param]})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
