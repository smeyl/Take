import time
import threading
import pyaudio

TARGET_IP = "127.0.0.1"  # change this for real network testing

import watcher
import artist
from artist import run_watcher, run_stream, stop_event
from watcher import WATCH_PATH

# Propagate TARGET_IP to both modules that reference it at call time
watcher.TARGET_IP = TARGET_IP
artist.TARGET_IP = TARGET_IP

STREAM_PORT = 5002
FILE_PORT = 5001

if __name__ == "__main__":
    threads = [
        threading.Thread(target=run_watcher, name="watcher", daemon=True),
        threading.Thread(target=run_stream, name="stream", daemon=True),
    ]
    for t in threads:
        t.start()

    print("Take — artist ready")
    print(f"  Watching       : {WATCH_PATH}")
    print(f"  File transfer  : {TARGET_IP}:{FILE_PORT}")
    print(f"  Audio stream   : {TARGET_IP}:{STREAM_PORT}")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        stop_event.set()
        for t in threads:
            t.join()
        print("Stopped.")
