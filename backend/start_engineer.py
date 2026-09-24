import os
import signal
import socket
import sys
import threading
import time
import requests
import pyaudio

import bounce
import engineer  # wires up receiver.on_file_received as a side effect
import ports
import daw
import record_watcher
import stream_sender
import timecode
from engineer import run_receiver, INCOMING_PATH, PORT

RELAY_URL = "http://127.0.0.1:5010"
TRANSPORT_PORT = 5004
STREAM_PORT = 5002
CHUNK = 1024
RATE = 44100
FORMAT = pyaudio.paInt16
CHANNELS = 1

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


def _find_output_device(audio, wanted):
    """Output device named exactly `wanted`, else the first whose name
    contains it. Returns (index, name) or (None, None)."""
    outputs = [(i, audio.get_device_info_by_index(i)) for i in range(audio.get_device_count())]
    outputs = [(i, d["name"]) for i, d in outputs if d.get("maxOutputChannels", 0) > 0]
    for i, name in outputs:
        if name == wanted:
            return i, name
    for i, name in outputs:
        if wanted in name:
            return i, name
    return None, None


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
    audio = pyaudio.PyAudio()

    wanted = daw.stream_device()
    dev_index, dev_name = _find_output_device(audio, wanted)

    # The artist's mic goes to the DAW's virtual input device ONLY — the DAW
    # records/monitors it from there. Never open the default output here: that
    # would play the mic directly on the engineer's speakers on top of the
    # DAW's monitoring.
    dev_stream = None
    if dev_index is not None:
        try:
            dev_stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                                    output=True, output_device_index=dev_index,
                                    frames_per_buffer=CHUNK)
            print(f"Stream receiver: artist mic → {dev_name} ({daw.NAME} input)")
        except Exception as e:
            print(f"Stream receiver: opening {dev_name} failed ({e})")
    if dev_stream is None:
        print(f"Stream receiver: no output device matching '{wanted}' — artist "
              f"mic will be received but NOT fed to {daw.NAME}. Set "
              f"TAKE_STREAM_DEVICE to the virtual device {daw.NAME} records "
              f"the artist from.", flush=True)

    try:
        while not stop_event.is_set():
            try:
                # Largest packet: 1 header byte + CHUNK samples of float32
                data, _ = sock.recvfrom(CHUNK * 4 + 1)
            except socket.timeout:
                continue
            if dev_stream:
                dev_stream.write(stream_sender.decode_to_int16(data))
    finally:
        if dev_stream:
            dev_stream.stop_stream()
            dev_stream.close()
        audio.terminate()
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
