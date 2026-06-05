import json
import os
import signal
import socket
import sys
import time
import threading
import requests

RELAY_URL = "http://127.0.0.1:5010"

import watcher
import artist
import backing_player
import cue_receiver
import stream_receiver
import stream_sender
import timecode
import transport
from artist import run_watcher, run_stream, stop_event
from backing_player import run_backing_player, BACKING_PATH
from cue_receiver import listen_for_cues
from stream_receiver import run_stream_receiver
from watcher import WATCH_PATH

STREAM_PORT = 5002
FILE_PORT = 5001
SESSION_FILE = "/tmp/take_session.json"


def get_local_ip():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]


def run_heartbeat(relay_url, code, stop_evt, on_dead):
    engineer_was_alive = None
    missed = 0
    while not stop_evt.is_set():
        try:
            requests.post(f"{relay_url}/session/{code}/heartbeat",
                          json={"role": "artist"}, timeout=3)
        except requests.RequestException:
            pass
        try:
            r = requests.get(f"{relay_url}/session/{code}/status", timeout=3)
            if r.ok:
                engineer_alive = r.json()["engineer"]
                if engineer_alive:
                    if engineer_was_alive is False:
                        print("✓ Engineer reconnected", flush=True)
                    missed = 0
                else:
                    missed += 1
                    if engineer_was_alive is True:
                        print("⚠ Engineer disconnected", flush=True)
                    if missed >= 5 and not stop_evt.is_set():
                        on_dead()
                        return
                engineer_was_alive = engineer_alive
        except requests.RequestException:
            pass
        stop_evt.wait(5)


def _read_session_file():
    for _ in range(120):
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE) as f:
                    data = json.load(f)
                os.unlink(SESSION_FILE)
                ip = data.get("engineer_ip", "")
                code = data.get("code", "")
                if ip and code:
                    return ip, code
            except Exception:
                pass
        time.sleep(1)
    return None, None


if __name__ == "__main__":
    print("Waiting for session code from JUCE app...", flush=True)
    TARGET_IP, code = _read_session_file()

    if TARGET_IP is None:
        code = input("Enter session code: ")

    local_ip = get_local_ip()
    resp = requests.post(f"{RELAY_URL}/session/join",
                         json={"code": code, "ip": local_ip}, timeout=5)
    resp.raise_for_status()
    TARGET_IP = resp.json()["engineer_ip"]

    print(f"Engineer found — {TARGET_IP}")

    watcher.TARGET_IP = TARGET_IP
    artist.TARGET_IP = TARGET_IP

    shutdown_reason = [None]

    def shutdown(reason=None):
        if stop_event.is_set():
            return
        shutdown_reason[0] = reason
        stop_event.set()
        backing_player.stop_event.set()
        cue_receiver.stop_event.set()

    signal.signal(signal.SIGINT, lambda sig, frame: shutdown())
    signal.signal(signal.SIGTERM, lambda sig, frame: shutdown())

    threads = [
        threading.Thread(target=run_watcher, name="watcher", daemon=True),
        threading.Thread(target=run_stream, args=(cue_receiver.params,), name="stream", daemon=True),
        threading.Thread(target=run_stream_receiver, args=(stop_event,), name="stream-receiver", daemon=True),
        threading.Thread(target=run_backing_player, name="backing-player", daemon=True),
        threading.Thread(target=listen_for_cues, name="cue-receiver", daemon=True),
        threading.Thread(
            target=transport.app.run,
            kwargs={"host": "0.0.0.0", "port": transport.PORT, "use_reloader": False},
            name="transport",
            daemon=True,
        ),
        threading.Thread(
            target=stream_sender.run_flask,
            name="stream-quality",
            daemon=True,
        ),
        threading.Thread(
            target=run_heartbeat,
            args=(RELAY_URL, code, stop_event,
                  lambda: shutdown("Session ended — engineer disconnected")),
            name="heartbeat",
            daemon=True,
        ),
        threading.Thread(target=timecode.receiver, args=(stop_event,),
                         name="timecode", daemon=True),
    ]
    for t in threads:
        t.start()

    print("Take — artist ready")
    print(f"  Watching        : {WATCH_PATH}")
    print(f"  File transfer   : {TARGET_IP}:{FILE_PORT}")
    print(f"  Mic stream out  : {TARGET_IP}:{STREAM_PORT}")
    print(f"  Stream in (DSP) : UDP 0.0.0.0:{stream_receiver.PORT}")
    print(f"  Cue params      : UDP 0.0.0.0:{cue_receiver.PORT}")
    print(f"  Backing player  : {BACKING_PATH}")
    print(f"  Transport       : 0.0.0.0:{transport.PORT}")
    print(f"  Timecode        : UDP 0.0.0.0:{timecode.PORT}")
    print(f"  Stream quality  : 0.0.0.0:{stream_sender.FLASK_PORT}")
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
