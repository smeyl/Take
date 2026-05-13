import socket
import time
import threading
import requests

RELAY_URL = "http://192.0.2.10:5010"

import watcher
import artist
import backing_player
import cue_receiver
from artist import run_watcher, run_stream, stop_event
from backing_player import run_backing_player, BACKING_PATH
from cue_receiver import listen_for_cues
from watcher import WATCH_PATH

STREAM_PORT = 5002
FILE_PORT = 5001


def get_local_ip():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]


if __name__ == "__main__":
    code = input("Enter session code: ")
    local_ip = get_local_ip()

    resp = requests.post(f"{RELAY_URL}/session/join", json={"code": code, "ip": local_ip})
    resp.raise_for_status()
    TARGET_IP = resp.json()["engineer_ip"]
    print(f"Engineer found — {TARGET_IP}")

    watcher.TARGET_IP = TARGET_IP
    artist.TARGET_IP = TARGET_IP

    threads = [
        threading.Thread(target=run_watcher, name="watcher", daemon=True),
        threading.Thread(target=run_stream, args=(cue_receiver.params,), name="stream", daemon=True),
        threading.Thread(target=run_backing_player, name="backing-player", daemon=True),
        threading.Thread(target=listen_for_cues, name="cue-receiver", daemon=True),
    ]
    for t in threads:
        t.start()

    print("Take — artist ready")
    print(f"  Watching       : {WATCH_PATH}")
    print(f"  File transfer  : {TARGET_IP}:{FILE_PORT}")
    print(f"  Audio stream   : {TARGET_IP}:{STREAM_PORT}")
    print(f"  Backing player : {BACKING_PATH}")
    print(f"  Cue mix receiver: UDP 0.0.0.0:{cue_receiver.PORT}")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        stop_event.set()
        backing_player.stop_event.set()
        cue_receiver.stop_event.set()
        for t in threads:
            t.join()
        print("Stopped.")
