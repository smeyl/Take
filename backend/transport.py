import logging
import math
import os
import queue
import threading
import time
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
import numpy as np
import pyaudio
import requests
import soundfile as sf
import backing_player
import cue_receiver

logging.getLogger("werkzeug").setLevel(logging.ERROR)

# Data lives at the repo root (sibling of this backend/ folder), not inside it.
RECORDINGS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "recordings")
PORT = 5004
RATE = 44100
CHANNELS = 1
_SYNC_FORMAT_FILE = "/tmp/take_sync_format"

# Relay on the engineer's machine — set by start_artist.py once the session is
# joined. Reaper transport commands must run there, not on this machine.
RELAY_URL = "http://127.0.0.1:5010"


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

# The artist app shows a 3-2-1 countdown when /status flips to recording.
# Actual capture (file write AND the Reaper transport start) is delayed by the
# same duration so the countdown is pure preparation time — nothing recorded
# during it, and the lossless file stays aligned with Reaper's timeline.
COUNTDOWN_SECONDS = 3  # must match the artist app's countdown (3 ticks x 1s)
_pending = None        # {"timer": threading.Timer, "cancelled": bool} during countdown


def _reaper_start():
    try:
        requests.post(f"{RELAY_URL}/reaper/record", timeout=5)
    except requests.RequestException:
        pass


def _reaper_stop():
    try:
        requests.post(f"{RELAY_URL}/reaper/stop", timeout=5)
    except requests.RequestException:
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
        # Without this stream there are no meters, no mic stream to the
        # engineer, and nothing to record — never die silently.
        print("FATAL: could not open any audio input device — check microphone "
              "permissions (System Settings → Privacy) and that an input device "
              "exists. No levels, no stream, no recording.", flush=True)
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
            chunk = mono.astype(np.float32) / 32768.0
            _write_queue.put(chunk.reshape(-1, CHANNELS).copy())

        # Stream feed — consumed by run_stream_from_transport(). Never block
        # the audio thread: if the consumer stalls, drop the oldest chunk.
        try:
            _stream_queue.put_nowait(mono)
        except queue.Full:
            try:
                _stream_queue.get_nowait()
                _stream_queue.put_nowait(mono)
            except (queue.Empty, queue.Full):
                pass

    stream.stop_stream()
    stream.close()
    if cue_out is not None:
        cue_out.stop_stream()
        cue_out.close()
    pa.terminate()


threading.Thread(target=_audio_thread, daemon=True).start()


def _open_take_file(fmt, take, timestamp):
    if fmt == "FLAC":
        path = os.path.join(RECORDINGS_PATH, f"T{take}_{timestamp}.flac")
        return sf.SoundFile(path, mode="w", samplerate=RATE, channels=CHANNELS,
                            format="FLAC", subtype="PCM_24")
    if fmt == "WAV32f":
        path = os.path.join(RECORDINGS_PATH, f"T{take}_{timestamp}.wav")
        return sf.SoundFile(path, mode="w", samplerate=RATE, channels=CHANNELS, subtype="FLOAT")
    # WAV24 (default)
    path = os.path.join(RECORDINGS_PATH, f"T{take}_{timestamp}.wav")
    return sf.SoundFile(path, mode="w", samplerate=RATE, channels=CHANNELS, subtype="PCM_24")


def _begin_capture(token, fmt, take, timestamp):
    """Countdown finished: open the file, start the writer, roll Reaper.
    The file must not exist before this point — watcher.py sends any audio
    file whose size stays stable, so an empty file idling through the
    countdown would be shipped as an empty take."""
    global _recording, _sf_file, _writer_thread, _stop_writer, _pending
    with _lock:
        if token["cancelled"]:   # /stop won the race — never start
            return
        _pending = None
        _sf_file = _open_take_file(fmt, take, timestamp)
        _stop_writer = threading.Event()
        _writer_thread = threading.Thread(target=_writer, args=(_sf_file, _stop_writer), daemon=True)
        _writer_thread.start()
        _recording = True
        threading.Thread(target=_reaper_start, daemon=True).start()
        print(f"Recording started — T{take}", flush=True)


@app.route("/record", methods=["POST"])
def record():
    global _take, _pending
    with _lock:
        if _recording or _pending is not None:
            return jsonify({"error": "already recording"}), 409
        _take += 1
        os.makedirs(RECORDINGS_PATH, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Format and Reaper track come from the relay proxy (engineer machine);
        # the /tmp fallbacks only work when both roles share one machine.
        data = request.get_json(force=True, silent=True) or {}
        fmt = data.get("format") or _get_sync_format()
        # Report recording=true immediately so the artist app starts its
        # countdown; actual capture begins when the countdown ends.
        token = {"cancelled": False}
        timer = threading.Timer(COUNTDOWN_SECONDS, _begin_capture,
                                args=(token, fmt, _take, timestamp))
        timer.daemon = True
        # deadline lets /status report the seconds remaining, so both apps
        # can show a synced countdown off one source of truth.
        _pending = {"timer": timer, "token": token,
                    "deadline": time.monotonic() + COUNTDOWN_SECONDS}
        timer.start()
        print(f"Record armed — T{_take} starts in {COUNTDOWN_SECONDS}s", flush=True)
        return jsonify({"recording": True, "take": _take,
                        "countdown": COUNTDOWN_SECONDS})


@app.route("/stop", methods=["POST"])
def stop():
    global _recording, _sf_file, _writer_thread, _pending
    with _lock:
        if _pending is not None:
            # Stopped during the countdown — nothing was captured yet
            _pending["token"]["cancelled"] = True
            _pending["timer"].cancel()
            _pending = None
            print(f"Recording cancelled during countdown — T{_take}", flush=True)
            return jsonify({"recording": False, "take": _take})
        if not _recording:
            return jsonify({"error": "not recording"}), 409
        _recording = False       # audio thread stops feeding the queue
        _stop_writer.set()
        _writer_thread.join()    # drain any buffered chunks before closing
        _sf_file.close()
        _sf_file = None
        threading.Thread(target=_reaper_stop, daemon=True).start()
        print(f"Recording stopped — T{_take} saved", flush=True)
        return jsonify({"recording": False, "take": _take})


@app.route("/status", methods=["GET"])
def status():
    with _lock:
        # Countdown counts as "recording" for every consumer: the artist app
        # keys its 3-2-1 off this flag and the engineer UI shows the live take.
        active = _recording or _pending is not None
        # countdown = whole seconds left before capture actually begins (0 when
        # not counting). Both the artist and engineer UIs render their 3-2-1
        # from this single value.
        countdown = 0
        if _pending is not None:
            countdown = max(0, min(COUNTDOWN_SECONDS,
                                   math.ceil(_pending["deadline"] - time.monotonic())))
        # backing_duration = real length of the loaded backing track (0 if none),
        # so the artist app's waveform ruler shows the true track length.
        return jsonify({"recording": active, "take": _take, "countdown": countdown,
                        "backing_duration": round(backing_player.duration, 3)})


@app.route("/levels", methods=["GET"])
def get_levels():
    return jsonify(levels)


@app.route("/cue/local/<param>/<int:value>", methods=["POST"])
def cue_local(param, value):
    if param not in cue_receiver.params:
        return jsonify({"error": "unknown param"}), 400
    cue_receiver.params[param] = max(0, min(100, value))
    return jsonify({"ok": True, "param": param, "value": cue_receiver.params[param]})


@app.route("/cue/params", methods=["GET"])
def cue_params():
    """Current cue-mix values — reflects both the engineer's changes (arriving
    via cue_receiver's UDP listener) and the artist's own local adjustments.
    The artist app polls this to keep its knob visuals in sync."""
    return jsonify(dict(cue_receiver.params))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
