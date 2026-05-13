import curses
import signal
import socket
import sys
import threading
import time
import requests
import pyaudio

import engineer  # wires up receiver.on_file_received as a side effect
import cue_sender
import timecode
from engineer import run_receiver, INCOMING_PATH, PORT, ACTION_INSERT_MEDIA
from reaper import BASE

RELAY_URL = "http://192.0.2.10:5010"
TRANSPORT_PORT = 5004
STREAM_PORT = 5002
CHUNK = 1024
RATE = 44100
FORMAT = pyaudio.paInt16
CHANNELS = 1

stop_event = threading.Event()


def engineer_record():
    try:
        r = requests.post(f"http://{cue_sender.TARGET_IP}:{TRANSPORT_PORT}/record", timeout=5)
        if r.ok:
            cue_sender.transport_status.update(r.json())
    except requests.RequestException:
        pass


def engineer_stop():
    try:
        r = requests.post(f"http://{cue_sender.TARGET_IP}:{TRANSPORT_PORT}/stop", timeout=5)
        if r.ok:
            cue_sender.transport_status.update(r.json())
    except requests.RequestException:
        pass


def engineer_status():
    try:
        r = requests.get(f"http://{cue_sender.TARGET_IP}:{TRANSPORT_PORT}/status", timeout=5)
        if r.ok:
            cue_sender.transport_status.update(r.json())
    except requests.RequestException:
        pass


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
    except requests.ConnectionError:
        return False


def run_stream_receiver():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", STREAM_PORT))
    sock.settimeout(1.0)
    audio = pyaudio.PyAudio()
    stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                        output=True, frames_per_buffer=CHUNK)
    try:
        while not stop_event.is_set():
            try:
                data, _ = sock.recvfrom(CHUNK * 2)
                stream.write(data)
            except socket.timeout:
                continue
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()
        sock.close()


if __name__ == "__main__":
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

    cue_sender.TARGET_IP = artist_ip
    cue_sender.transport_callbacks["record"] = engineer_record
    cue_sender.transport_callbacks["stop"] = engineer_stop
    cue_sender.transport_callbacks["status"] = engineer_status
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
    print(f"  Cue mix sender : UDP → {cue_sender.TARGET_IP}:{cue_sender.PORT}")
    print(f"  Timecode       : UDP → {artist_ip}:{timecode.PORT}")
    print("Press Ctrl+C to stop.\n")

    cue_thread = threading.Thread(target=curses.wrapper, args=(cue_sender.main,),
                                  name="cue-sender", daemon=True)
    cue_thread.start()
    threads.append(cue_thread)

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
