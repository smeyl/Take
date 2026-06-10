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
_SYNC_FORMAT_FILE = "/tmp/take_sync_format"


def _get_sync_format():
    try:
        with open(_SYNC_FORMAT_FILE) as fh:
            return fh.read().strip()
    except OSError:
        return "WAV24"

app = Flask(__name__)
CORS(app)

levels = {"l": -60.0, "r": -60.0}

_lock = threading.Lock()
_recording = False
_take = 0
_sf_file = None
_write_queue = queue.Queue()
_stream_queue = queue.Queue(maxsize=32)  # mic audio for run_stream_from_transport
_stop_writer = threading.Event()
_writer_thread = None
_rec_chunk_count = 0


def _get_dest_track():
    try:
        with open("/tmp/take_dest_track") as f:
            return int(f.read().strip())
    except Exception:
        return 0


def _reaper_start(track):
    try:
        import reaper
        reaper.arm_track_by_index(track)
        reaper.start_recording()
    except Exception:
        pass


def _reaper_stop():
    try:
        import reaper
        reaper.stop_recording()
    except Exception:
        pass


def run_stream_from_transport():
    """Read mic chunks from the shared _stream_queue — avoids opening a second input stream."""
    import stream_sender
    import watcher
    STREAM_PORT = 5002
    import socket as _socket
    sock = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
    while True:
        try:
            chunk = _stream_queue.get(timeout=1.0)
        except queue.Empty:
            continue
        data = stream_sender.encode(chunk.tobytes())
        sock.sendto(data, (watcher.TARGET_IP, STREAM_PORT))


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

    cue_out = None
    try:
        cue_out = pa.open(format=pyaudio.paInt16, channels=CHANNELS, rate=RATE,
                          output=True, frames_per_buffer=CHUNK)
    except Exception as e:
        print(f"[transport] cue output open failed: {e}", flush=True)

    while True:
        try:
            raw = stream.read(CHUNK, exception_on_overflow=False)
        except OSError:
            break

        # Mono int16 — shared by cue, stream, and recording paths
        mono = (np.frombuffer(raw, dtype=np.int16) if ch == 1
                else np.frombuffer(raw, dtype=np.int16).reshape(-1, ch).mean(axis=1).astype(np.int16))

        # Meter — always running (uses raw pre-downmix for true stereo L/R)
        raw_f = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        if ch >= 2:
            lr = raw_f.reshape(-1, ch)
            l_rms = float(np.sqrt(np.mean(lr[:, 0] ** 2)))
            r_rms = float(np.sqrt(np.mean(lr[:, 1] ** 2)))
        else:
            l_rms = r_rms = float(np.sqrt(np.mean(raw_f ** 2)))
        levels["l"] = max(-60.0, min(0.0, 20.0 * math.log10(l_rms + 1e-9)))
        levels["r"] = max(-60.0, min(0.0, 20.0 * math.log10(r_rms + 1e-9)))

        # Direct cue monitoring — no UDP round-trip
        if cue_out is not None:
            try:
                cue_out.write(cue_receiver.process_audio(mono).tobytes())
            except Exception:
                pass

        # Recording feed — only when active
        if _recording:
            global _rec_chunk_count
            chunk = mono.astype(np.float32) / 32768.0
            chunk *= 0.5
            _rec_chunk_count += 1
            if _rec_chunk_count % 100 == 0:
                print(f"[rec] max after gain: {np.abs(chunk).max():.4f}", flush=True)
            _write_queue.put(chunk.reshape(-1, CHANNELS).copy())

        # Stream feed — always running, consumed by run_stream_from_transport()
        _stream_queue.put(mono)

    stream.stop_stream()
    stream.close()
    if cue_out is not None:
        cue_out.stop_stream()
        cue_out.close()
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
        fmt = _get_sync_format()
        if fmt == "FLAC":
            path = os.path.join(RECORDINGS_PATH, f"T{_take}_{timestamp}.flac")
            _sf_file = sf.SoundFile(path, mode="w", samplerate=RATE, channels=CHANNELS,
                                    format="FLAC", subtype="PCM_24")
        elif fmt == "WAV32f":
            path = os.path.join(RECORDINGS_PATH, f"T{_take}_{timestamp}.wav")
            _sf_file = sf.SoundFile(path, mode="w", samplerate=RATE, channels=CHANNELS, subtype="FLOAT")
        else:  # WAV24 (default)
            path = os.path.join(RECORDINGS_PATH, f"T{_take}_{timestamp}.wav")
            _sf_file = sf.SoundFile(path, mode="w", samplerate=RATE, channels=CHANNELS, subtype="PCM_24")
        _stop_writer = threading.Event()
        _writer_thread = threading.Thread(target=_writer, args=(_sf_file, _stop_writer), daemon=True)
        _writer_thread.start()
        _recording = True
        track = _get_dest_track()
        threading.Thread(target=_reaper_start, args=(track,), daemon=True).start()
        print(f"Recording started — T{_take} at {datetime.now().strftime('%H:%M:%S.%f')[:-3]} (Reaper track {track})", flush=True)
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
        threading.Thread(target=_reaper_stop, daemon=True).start()
        print(f"Recording stopped — T{_take} saved at {datetime.now().strftime('%H:%M:%S.%f')[:-3]}", flush=True)
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
