import os
import signal
import socket
import sys
import threading
import time
import numpy as np
import requests
import sounddevice as sd

import bounce
import engineer  # wires up receiver.on_file_received as a side effect
import ports
import daw
import record_watcher
import stream_sender
from resampler import Resampler
import timecode
from engineer import run_receiver, INCOMING_PATH, PORT

RELAY_URL = "http://127.0.0.1:5010"
TRANSPORT_PORT = 5004
STREAM_PORT = 5002
STREAM_RATE = 44100   # the artist's live stream wire format
MAX_PACKET = 4 * 1024 + 1  # 1 header byte + 1024 float32 samples (largest the sender makes)
# Audio held in reserve against network jitter before the artist's stream is
# played to the DAW. This is a fixed part of the monitoring delay: bigger
# rides out a worse connection, smaller is tighter.
STREAM_BUFFER_MS = float(os.environ.get("TAKE_STREAM_BUFFER_MS", "40"))
# How far past the reserve the buffer may fill (a packet plus an audio block
# arriving together) before the excess is dropped back down to the reserve.
STREAM_EXCESS_MS = 15
# Once a second the average depth is checked: off the reserve by more than
# this (audio lost upstream, or clock drift between the two machines) and it
# is put back — silence added or audio dropped — so the delay stays fixed.
STREAM_TOLERANCE_MS = 8

stop_event = threading.Event()


def run_heartbeat(relay_url, code, stop_evt, on_dead):
    artist_was_alive = None
    missed = 0
    while not stop_evt.is_set():
        try:
            requests.post(f"{relay_url}/session/{code}/heartbeat",
                          json={"role": "engineer"}, timeout=3)
        except requests.RequestException:
            pass
        try:
            r = requests.get(f"{relay_url}/session/{code}/status", timeout=3)
            if r.ok:
                artist_alive = r.json()["artist"]
                if artist_alive:
                    if artist_was_alive is False:
                        print("✓ Artist reconnected", flush=True)
                    missed = 0
                else:
                    missed += 1
                    if artist_was_alive is True:
                        print("⚠ Artist disconnected", flush=True)
                    if missed >= 2 and not stop_evt.is_set():
                        on_dead()
                        return
                artist_was_alive = artist_alive
        except requests.RequestException:
            pass
        stop_evt.wait(5)


def get_local_ip():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]


def _find_output_device(wanted):
    """Output device named exactly `wanted`, else the first whose name
    contains it. Returns (index, name) or (None, None)."""
    outputs = [(i, d["name"]) for i, d in enumerate(sd.query_devices())
               if d["max_output_channels"] > 0]
    for i, name in outputs:
        if name == wanted:
            return i, name
    for i, name in outputs:
        if wanted in name:
            return i, name
    return None, None


class _JitterBuffer:
    """Artist audio waiting to be played to the DAW, kept at a fixed depth so
    the delay it adds is fixed: it starts playing once `target` samples are
    in; a burst that fills it past `limit` (backlog after a network stall or
    at startup) is dropped back to `target` at once; running dry plays
    silence and waits for `target` again. Slower shifts — audio that never
    arrived, or one machine's clock running faster — are corrected once a
    `window` of playback when the average depth is off by over `tolerance`."""

    def __init__(self, target, limit, tolerance, window):
        self.target, self.limit = target, limit
        self.tolerance, self.window = tolerance, window
        self.buf = np.zeros(0, dtype=np.float32)
        self.playing = False
        self.depth_sum = self.pulls = self.played = 0
        self.lock = threading.Lock()

    def push(self, x):
        with self.lock:
            self.buf = np.concatenate([self.buf, x])
            if len(self.buf) > self.limit:
                self.buf = self.buf[-self.target:]

    def pull(self, out):
        with self.lock:
            if not self.playing and len(self.buf) >= self.target:
                self.playing = True
            n = min(len(out), len(self.buf)) if self.playing else 0
            out[:n] = self.buf[:n]
            out[n:] = 0
            self.buf = self.buf[n:]
            if self.playing and n < len(out):
                self.playing = False
            if not self.playing:
                self.depth_sum = self.pulls = self.played = 0
                return
            self.depth_sum += len(self.buf)
            self.pulls += 1
            self.played += len(out)
            if self.played >= self.window:
                # Depth just after a pull averages the reserve in steady state.
                off = round(self.depth_sum / self.pulls) - self.target
                if off < -self.tolerance:
                    self.buf = np.concatenate([np.zeros(-off, dtype=np.float32), self.buf])
                elif off > self.tolerance:
                    self.buf = self.buf[off:]
                self.depth_sum = self.pulls = self.played = 0


def run_stream_receiver():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(("0.0.0.0", STREAM_PORT))
    except OSError:
        print(f"FATAL: stream receiver could not bind UDP {STREAM_PORT} — another "
              f"process owns it (lsof -i :{STREAM_PORT}). No live artist audio.",
              flush=True)
        return
    sock.settimeout(1.0)

    wanted = daw.stream_device()
    dev_index, dev_name = _find_output_device(wanted)

    # The artist's mic goes to the DAW's virtual input device ONLY — the DAW
    # records/monitors it from there. Never open the default output here: that
    # would play the mic directly on the engineer's speakers on top of the
    # DAW's monitoring.
    stream = jitter = resampler = None
    if dev_index is not None:
        try:
            # Played by a callback at the device's own rate (no blocking
            # writes, whose buffering grows with every network hiccup).
            rate = int(sd.query_devices(dev_index)["default_samplerate"])
            jitter = _JitterBuffer(round(STREAM_BUFFER_MS / 1000 * rate),
                                   round((STREAM_BUFFER_MS + STREAM_EXCESS_MS) / 1000 * rate),
                                   round(STREAM_TOLERANCE_MS / 1000 * rate), rate)
            resampler = Resampler(STREAM_RATE, rate)
            stream = sd.OutputStream(device=dev_index, samplerate=rate, channels=1,
                                     dtype="float32", blocksize=128, latency="low",
                                     callback=lambda out, frames, t, st: jitter.pull(out[:, 0]))
            stream.start()
            print(f"Stream receiver: artist mic → {dev_name} ({daw.NAME} input) @ "
                  f"{rate} Hz, {STREAM_BUFFER_MS:.0f} ms jitter buffer + "
                  f"{stream.latency * 1000:.1f} ms output", flush=True)
        except Exception as e:
            stream = None
            print(f"Stream receiver: opening {dev_name} failed ({e})")
    if stream is None:
        print(f"Stream receiver: no output device matching '{wanted}' — artist "
              f"mic will be received but NOT fed to {daw.NAME}. Set "
              f"TAKE_STREAM_DEVICE to the virtual device {daw.NAME} records "
              f"the artist from.", flush=True)

    try:
        while not stop_event.is_set():
            try:
                data, _ = sock.recvfrom(MAX_PACKET)
            except socket.timeout:
                continue
            if stream:
                pcm = np.frombuffer(stream_sender.decode_to_int16(data), dtype=np.int16)
                jitter.push(resampler.process(pcm.astype(np.float32) / 32768.0))
    finally:
        if stream:
            stream.stop()
            stream.close()
        sock.close()


if __name__ == "__main__":
    try:
        ports.ensure_free([
            (PORT,        "tcp", "file receiver"),
            (5006,        "tcp", "bounce server"),
            (STREAM_PORT, "udp", "artist mic stream"),
        ])

        local_ip = get_local_ip()

        # The relay is launched moments before us (dev_engineer.sh) and can
        # take a few seconds to bind on a first run with cold imports — retry
        # instead of crashing on the first refused connection.
        deadline = time.time() + 30
        while True:
            try:
                resp = requests.post(f"{RELAY_URL}/session/new",
                                     json={"ip": local_ip}, timeout=3)
                resp.raise_for_status()
                break
            except requests.RequestException:
                if time.time() > deadline:
                    print("Could not reach the relay on 127.0.0.1:5010 after 30s "
                          "— is relay.py running?", file=sys.stderr)
                    sys.exit(1)
                time.sleep(1)
        code = resp.json()["code"]

        display_code = f"{code[0:2]} · {code[2:4]} · {code[4:6]}"
        print(f"\nSession code: {display_code}\n")
        print("Waiting for artist to join...")

        artist_ip = None
        while artist_ip is None:
            time.sleep(2)
            try:
                r = requests.get(f"{RELAY_URL}/session/{code}", timeout=5)
                if r.status_code == 200:
                    artist_ip = r.json()["artist_ip"]
            except requests.RequestException:
                pass

        bounce.TARGET_IP = artist_ip
        print(f"Artist connected — {artist_ip}\n")

        daw_ok = daw.alive()

        shutdown_reason = [None]

        def shutdown(reason=None):
            if stop_event.is_set():
                return
            shutdown_reason[0] = reason
            stop_event.set()

        signal.signal(signal.SIGINT, lambda sig, frame: shutdown())
        signal.signal(signal.SIGTERM, lambda sig, frame: shutdown())

        threads = [
            threading.Thread(target=run_receiver, name="http-receiver", daemon=True),
            threading.Thread(target=bounce.run_bounce_server, name="bounce-server", daemon=True),
            threading.Thread(target=run_stream_receiver, name="stream-receiver", daemon=True),
            threading.Thread(
                target=run_heartbeat,
                args=(RELAY_URL, code, stop_event,
                      lambda: shutdown("Session ended — artist disconnected")),
                name="heartbeat",
                daemon=True,
            ),
            threading.Thread(target=timecode.sender, args=(artist_ip, stop_event),
                             name="timecode", daemon=True),
            # Record/Stop in Reaper's own transport drives the artist's capture.
            threading.Thread(target=record_watcher.run, args=(stop_event,),
                             name="record-watcher", daemon=True),
        ]
        for t in threads:
            t.start()

        print("Take — engineer ready")
        print(f"  File receiver  : 0.0.0.0:{PORT} → {INCOMING_PATH}/")
        print(f"  Stream receiver: UDP 0.0.0.0:{STREAM_PORT}")
        print(f"  Take script    : {'running in ' + daw.NAME if daw_ok else 'NOT RUNNING — start ' + daw.NAME + ' (its Take script loads automatically)'}")
        print(f"  Timecode       : UDP → {artist_ip}:{timecode.PORT}")
        print(f"  Recording      : follows {daw.NAME}'s Record/Stop")
        print("Press Ctrl+C to stop.\n")

        stop_event.wait()

        msg = shutdown_reason[0] or "Shutting down..."
        print(f"\n{msg}", flush=True)

        try:
            requests.delete(f"{RELAY_URL}/session/{code}", timeout=3)
        except requests.RequestException:
            pass

        for t in threads:
            t.join(timeout=2)

        sys.exit(0)

    except Exception as e:
        import traceback
        print(f"\n[CRASH] {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
