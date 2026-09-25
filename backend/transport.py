import collections
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
import requests
import sounddevice as sd
import soundfile as sf
import backing_player
import cue_receiver

logging.getLogger("werkzeug").setLevel(logging.ERROR)

# Data lives at the repo root (sibling of this backend/ folder), not inside it.
RECORDINGS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "recordings")
PORT = 5004
STREAM_RATE = 44100   # the live stream to the engineer is always 44.1 kHz int16
STREAM_CHUNK = 256    # samples per stream packet (5.8 ms)
BLOCK = 128           # audio callback block: ~2.7 ms at 48 kHz
CHANNELS = 1
# Optional device overrides (name, or part of it) — e.g. an audio interface.
# Default: the system's input/output devices.
INPUT_DEVICE = os.environ.get("TAKE_INPUT_DEVICE") or None
OUTPUT_DEVICE = os.environ.get("TAKE_OUTPUT_DEVICE") or None
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
    # Tell the DAW where in the backing track the artist was when the first
    # recorded sample was captured — the position they were performing to.
    # That is where the take belongs; the DAW's own "now" is later by the
    # network round trip plus both machines' audio latencies.
    body = {}
    deadline = time.monotonic() + 0.5
    while capture["t0"] is None and time.monotonic() < deadline:
        time.sleep(0.005)
    if capture["t0"] is not None:
        heard = backing_player.heard_position(capture["t0"])
        if heard is not None:
            body["capture_pos"] = round(heard, 6)
    try:
        requests.post(f"{RELAY_URL}/reaper/record", json=body, timeout=5)
    except requests.RequestException:
        pass


def _reaper_stop():
    try:
        requests.post(f"{RELAY_URL}/reaper/stop", timeout=5)
    except requests.RequestException:
        pass


class _Resampler:
    """Streaming linear-interpolation resampler (for the monitoring-only live
    stream; the recording is written at the device's native rate)."""

    def __init__(self, src_rate, dst_rate):
        self.step = src_rate / dst_rate
        self.buf = np.zeros(0, dtype=np.float32)
        self.t = 0.0

    def process(self, x):
        self.buf = np.concatenate([self.buf, x])
        if len(self.buf) < 2:
            return np.zeros(0, dtype=np.float32)
        n = int((len(self.buf) - 1 - self.t) / self.step) + 1
        idx = self.t + np.arange(n) * self.step
        i0 = idx.astype(np.int64)
        frac = (idx - i0).astype(np.float32)
        i1 = np.minimum(i0 + 1, len(self.buf) - 1)
        out = self.buf[i0] * (1.0 - frac) + self.buf[i1] * frac
        nxt = self.t + n * self.step
        drop = int(nxt)
        self.buf, self.t = self.buf[drop:], nxt - drop
        return out


def run_stream_from_transport():
    """Send the mic to the engineer: native-rate blocks from the input callback,
    resampled to 44.1 kHz int16 and packetised (the stream's wire format)."""
    import stream_sender
    import watcher
    STREAM_PORT = 5002
    import socket as _socket
    sock = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
    while not _audio_ready.wait(1.0):
        pass
    resampler = _Resampler(audio["rate"], STREAM_RATE)
    pending = np.zeros(0, dtype=np.float32)
    while True:
        try:
            block = _stream_queue.get(timeout=1.0)
        except queue.Empty:
            continue
        pending = np.concatenate([pending, resampler.process(block)])
        while len(pending) >= STREAM_CHUNK:
            chunk, pending = pending[:STREAM_CHUNK], pending[STREAM_CHUNK:]
            pcm = (np.clip(chunk, -1.0, 1.0) * 32767.0).astype(np.int16)
            sock.sendto(stream_sender.encode(pcm.tobytes()), (watcher.TARGET_IP, STREAM_PORT))


def _writer(sf_file, stop_evt):
    while not stop_evt.is_set() or not _write_queue.empty():
        try:
            data = _write_queue.get(timeout=0.1)
            sf_file.write(data)
        except queue.Empty:
            continue


# ── Audio engine ──────────────────────────────────────────────────────────────
# Two callback streams at the input device's native rate: the mic input, and
# the cue-mix monitor output. They are separate streams on purpose — opening
# one full-duplex stream across two devices (built-in mic + headphones) makes
# PortAudio add ~85 ms of buffering to bridge their clocks. Blocking I/O and a
# sample-rate mismatch (44.1 kHz streams on 48 kHz hardware) cost far more.

audio = {"rate": None, "input_latency": 0.0, "output_latency": 0.0,
         "underruns": 0, "trimmed": 0}
_audio_ready = threading.Event()
# Mic blocks waiting for the output callback. The input callback arrives in
# bursts (the hardware delivers 512 frames = 4 blocks at once) while the output
# pulls one block every ~2.7 ms, so this buffer must hold a whole burst. The
# output callback keeps it minimal: if it never ran below 2 blocks over the
# last ~0.5 s, it drops one (clock drift between the two devices), and an
# empty buffer plays one block of silence (which re-adds a block of cushion).
_monitor = collections.deque()
MONITOR_HARD_CAP = 32              # memory bound only; normal depth is 0-5 blocks
TRIM_WINDOW = 200                  # output callbacks (~0.5 s at 48 kHz / 128)
_trim = {"min": MONITOR_HARD_CAP, "n": 0}
_level_window = collections.deque(maxlen=16)   # ~40 ms of per-block mean squares
capture = {"t0": None}             # host time of the first recorded sample (ADC)


def _find_device(name, kind):
    """Device named exactly `name`, else the first whose name contains it."""
    if not name:
        return None
    devices = [(i, d["name"]) for i, d in enumerate(sd.query_devices())
               if d[f"max_{kind}_channels"] > 0]
    for i, dev_name in devices:
        if dev_name == name:
            return i
    for i, dev_name in devices:
        if name.lower() in dev_name.lower():
            return i
    print(f"[transport] no {kind} device matching '{name}' — using the default", flush=True)
    return None


def _on_input(indata, frames, t, status):
    mono = indata.mean(axis=1) if indata.shape[1] > 1 else indata[:, 0].copy()

    # Meters — stereo inputs show L/R, mono shows the same on both.
    _level_window.append(np.mean(indata[:, :2] ** 2, axis=0))
    ms = np.mean(np.array(_level_window), axis=0)
    l_ms, r_ms = (ms[0], ms[1]) if ms.shape[0] > 1 else (ms[0], ms[0])
    levels["l"] = max(-60.0, min(0.0, 10.0 * math.log10(l_ms + 1e-12)))
    levels["r"] = max(-60.0, min(0.0, 10.0 * math.log10(r_ms + 1e-12)))

    # Monitor — straight to the output callback (see _monitor above).
    _monitor.append(mono)
    while len(_monitor) > MONITOR_HARD_CAP:
        _monitor.popleft()

    # Recording — the first block after capture begins also fixes the capture
    # start time (the ADC time of its first sample).
    if _recording:
        if capture["t0"] is None:
            capture["t0"] = t.inputBufferAdcTime
        _write_queue.put(mono.reshape(-1, CHANNELS).copy())

    # Live stream — never block the audio callback; drop the oldest if the
    # sender thread stalls.
    try:
        _stream_queue.put_nowait(mono)
    except queue.Full:
        try:
            _stream_queue.get_nowait()
            _stream_queue.put_nowait(mono)
        except (queue.Empty, queue.Full):
            pass


def _on_output(outdata, frames, t, status):
    depth = len(_monitor)
    _trim["min"] = min(_trim["min"], depth)
    _trim["n"] += 1
    if _trim["n"] >= TRIM_WINDOW:
        if _trim["min"] >= 2 and _monitor:
            _monitor.popleft()          # standing excess latency — drop one block
            audio["trimmed"] += 1
        _trim.update(min=MONITOR_HARD_CAP, n=0)
    if _monitor:
        block = _monitor.popleft()
        if len(block) == frames:
            outdata[:, 0] = cue_receiver.process(block, audio["rate"])
            return
    else:
        audio["underruns"] += 1
    outdata.fill(0)


def _audio_thread():
    """Start the input and monitor-output callback streams and keep them open."""
    in_dev = _find_device(INPUT_DEVICE, "input")
    out_dev = _find_device(OUTPUT_DEVICE, "output")
    try:
        info = sd.query_devices(in_dev if in_dev is not None else sd.default.device[0])
        rate = int(info["default_samplerate"])
        channels = min(2, int(info["max_input_channels"])) or 1
        inp = sd.InputStream(device=in_dev, samplerate=rate, channels=channels, blocksize=BLOCK,
                             dtype="float32", latency="low", callback=_on_input)
    except Exception as e:
        # Without this stream there are no meters, no mic stream to the
        # engineer, and nothing to record — never die silently.
        print(f"FATAL: could not open the audio input ({e}) — check microphone "
              "permissions (System Settings → Privacy) and that an input device "
              "exists. No levels, no stream, no recording.", flush=True)
        return
    out = None
    try:
        out = sd.OutputStream(device=out_dev, samplerate=rate, channels=1, blocksize=BLOCK,
                              dtype="float32", latency="low", callback=_on_output)
    except Exception as e:
        print(f"[transport] cue monitor output failed ({e}) — no local monitoring", flush=True)
    audio.update(rate=rate, input_latency=inp.latency,
                 output_latency=out.latency if out is not None else 0.0)
    _audio_ready.set()
    inp.start()
    if out is not None:
        out.start()
    print(f"[transport] audio: {info['name']} @ {rate} Hz, input {inp.latency * 1000:.1f} ms, "
          f"monitor output {audio['output_latency'] * 1000:.1f} ms", flush=True)
    threading.Event().wait()   # keep the streams alive for the process lifetime


threading.Thread(target=_audio_thread, daemon=True).start()


def _open_take_file(fmt, take, timestamp):
    if fmt == "FLAC":
        path = os.path.join(RECORDINGS_PATH, f"T{take}_{timestamp}.flac")
        return sf.SoundFile(path, mode="w", samplerate=audio["rate"], channels=CHANNELS,
                            format="FLAC", subtype="PCM_24")
    if fmt == "WAV32f":
        path = os.path.join(RECORDINGS_PATH, f"T{take}_{timestamp}.wav")
        return sf.SoundFile(path, mode="w", samplerate=audio["rate"], channels=CHANNELS, subtype="FLOAT")
    # WAV24 (default)
    path = os.path.join(RECORDINGS_PATH, f"T{take}_{timestamp}.wav")
    return sf.SoundFile(path, mode="w", samplerate=audio["rate"], channels=CHANNELS, subtype="PCM_24")


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
        capture["t0"] = None     # set by the input callback on the first recorded block
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
