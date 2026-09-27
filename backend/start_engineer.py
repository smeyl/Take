import ipv4  # noqa: F401 — IPv4-only HTTP lookups (NAT64 networks); must come first
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


# The session being served: the relay's current one. Changes when the engineer
# app makes a new code ("Generate new code", or a fresh session after End
# Session), and its artist_ip is set once an artist joins it.
current = {"code": None, "artist_ip": None}


def _fmt(code):
    return f"{code[0:2]} · {code[2:4]} · {code[4:6]}"


def follow_session(relay_url, stop_evt):
    """Follow the relay's current session: switch to each new code, point the
    timecode and bounce at whichever artist joins it, and heartbeat it. An
    artist leaving doesn't stop anything — the backend waits for the next."""
    artist_was_alive = None
    next_heartbeat = 0.0
    while not stop_evt.is_set():
        try:
            r = requests.get(f"{relay_url}/session/current", timeout=3)
            session = r.json() if r.ok else None
        except (requests.RequestException, ValueError):
            session = None
        if session and session["code"] != current["code"]:
            current.update(code=session["code"], artist_ip=None)
            bounce.TARGET_IP = "127.0.0.1"
            artist_was_alive = None
            next_heartbeat = 0.0
            print(f"\nSession code: {_fmt(session['code'])}\nWaiting for artist to join...", flush=True)
        if session and session["artist_ip"] and session["artist_ip"] != current["artist_ip"]:
            current["artist_ip"] = session["artist_ip"]
            bounce.TARGET_IP = session["artist_ip"]
            print(f"Artist connected — {session['artist_ip']}", flush=True)

        if current["code"] and time.monotonic() >= next_heartbeat:
            next_heartbeat = time.monotonic() + 5
            code = current["code"]
            try:
                requests.post(f"{relay_url}/session/{code}/heartbeat",
                              json={"role": "engineer"}, timeout=3)
                st = requests.get(f"{relay_url}/session/{code}/status", timeout=3)
                if st.ok and current["artist_ip"]:
                    alive = st.json()["artist"]
                    if alive and artist_was_alive is False:
                        print("✓ Artist reconnected", flush=True)
                    elif not alive and artist_was_alive:
                        print("⚠ Artist disconnected — waiting for them to rejoin, "
                              "or for a new session", flush=True)
                    artist_was_alive = alive
            except (requests.RequestException, ValueError, KeyError):
                pass
        stop_evt.wait(0.25)


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
            # Part of the artist's backing-track advance (loop_latency.py).
            try:
                requests.post(f"{RELAY_URL}/latency/receiver",
                              json={"ms": STREAM_BUFFER_MS + stream.latency * 1000},
                              timeout=3)
            except requests.RequestException:
                print("Stream receiver: couldn't report its delay to the relay — "
                      "the artist's backing track won't be advanced for it", flush=True)
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

        daw_ok = daw.alive()

        shutdown_reason = [None]

        def shutdown(reason=None):
            if stop_event.is_set():
                return
            shutdown_reason[0] = reason
            stop_event.set()

        signal.signal(signal.SIGINT, lambda sig, frame: shutdown())
        signal.signal(signal.SIGTERM, lambda sig, frame: shutdown())

        # Everything runs from launch and follows the relay's current session
        # (follow_session): the engineer app can replace it at any time.
        # Record/Stop in the DAW's own transport drives the artist's capture;
        # the relay knows an artist the moment they join, so a Record pressed
        # right after is followed at once, and one pressed with no artist is
        # reported as not captured. Takes can arrive before a session's artist
        # has joined (one being captured while this backend restarted).
        threads = [
            threading.Thread(target=follow_session, args=(RELAY_URL, stop_event),
                             name="session", daemon=True),
            threading.Thread(target=record_watcher.run, args=(stop_event,),
                             name="record-watcher", daemon=True),
            threading.Thread(target=run_receiver, name="http-receiver", daemon=True),
            threading.Thread(target=bounce.run_bounce_server, name="bounce-server", daemon=True),
            threading.Thread(target=run_stream_receiver, name="stream-receiver", daemon=True),
            threading.Thread(target=timecode.sender, args=(lambda: current["artist_ip"], stop_event),
                             name="timecode", daemon=True),
        ]
        for t in threads:
            t.start()

        print("Take — engineer ready")
        print(f"  File receiver  : 0.0.0.0:{PORT} → {INCOMING_PATH}/")
        print(f"  Stream receiver: UDP 0.0.0.0:{STREAM_PORT}")
        print(f"  Take script    : {'running in ' + daw.NAME if daw_ok else 'NOT RUNNING — start ' + daw.NAME + ' (its Take script loads automatically)'}")
        print(f"  Timecode       : UDP → the session's artist, port {timecode.PORT}")
        print(f"  Recording      : follows {daw.NAME}'s Record/Stop")
        print("Press Ctrl+C to stop.\n")

        stop_event.wait()

        msg = shutdown_reason[0] or "Shutting down..."
        print(f"\n{msg}", flush=True)

        if current["code"]:
            try:
                requests.delete(f"{RELAY_URL}/session/{current['code']}", timeout=3)
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
