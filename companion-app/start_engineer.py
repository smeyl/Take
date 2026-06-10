import signal
import socket
import sys
import threading
import time
import requests
import pyaudio

import bounce
import engineer  # wires up receiver.on_file_received as a side effect
import stream_sender
import timecode
from engineer import run_receiver, INCOMING_PATH, PORT, ACTION_INSERT_MEDIA
from reaper import BASE

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


def check_reaper():
    try:
        requests.get(BASE, timeout=3)
        return True
    except Exception:
        return False


def _find_blackhole_device(audio):
    for i in range(audio.get_device_count()):
        info = audio.get_device_info_by_index(i)
        if "BlackHole" in info.get("name", "") and info.get("maxOutputChannels", 0) > 0:
            return i, info["name"]
    return None, None


def run_stream_receiver():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", STREAM_PORT))
    sock.settimeout(1.0)
    audio = pyaudio.PyAudio()

    bh_index, bh_name = _find_blackhole_device(audio)

    bh_stream = None
    if bh_index is not None:
        try:
            bh_stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                                   output=True, output_device_index=bh_index,
                                   frames_per_buffer=CHUNK)
            print(f"Stream receiver: BlackHole → {bh_name} (Reaper input)")
        except Exception as e:
            print(f"Stream receiver: BlackHole open failed ({e})")

    default_stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                                output=True, frames_per_buffer=CHUNK)
    print(f"Stream receiver: default output → speakers/headphones")

    def _write_parallel(data, streams):
        threads = [threading.Thread(target=s.write, args=(data,)) for s in streams if s]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    try:
        while not stop_event.is_set():
            try:
                # Largest packet: 1 header byte + CHUNK samples of float32
                data, _ = sock.recvfrom(CHUNK * 4 + 1)
                pcm = stream_sender.decode_to_int16(data)
                _write_parallel(pcm, [default_stream, bh_stream])
            except socket.timeout:
                continue
    finally:
        default_stream.stop_stream()
        default_stream.close()
        if bh_stream:
            bh_stream.stop_stream()
            bh_stream.close()
        audio.terminate()
        sock.close()


if __name__ == "__main__":
    try:
        local_ip = get_local_ip()
        resp = requests.post(f"{RELAY_URL}/session/new", json={"ip": local_ip})
        resp.raise_for_status()
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

        reaper_ok = check_reaper()

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
        ]
        for t in threads:
            t.start()

        print("Take — engineer ready")
        print(f"  File receiver  : 0.0.0.0:{PORT} → {INCOMING_PATH}/")
        print(f"  Stream receiver: UDP 0.0.0.0:{STREAM_PORT}")
        print(f"  Reaper         : {BASE} ({'reachable' if reaper_ok else 'NOT REACHABLE'})")
        print(f"  Script         : {ACTION_INSERT_MEDIA}")
        print(f"  Timecode       : UDP → {artist_ip}:{timecode.PORT}")
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
