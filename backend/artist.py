import os
import threading
import time
from watchdog.observers import Observer
from watcher import AudioHandler, WATCH_PATH

stop_event = threading.Event()


def run_watcher():
    os.makedirs(WATCH_PATH, exist_ok=True)
    observer = Observer()
    observer.schedule(AudioHandler(), WATCH_PATH, recursive=False)
    observer.start()
    stop_event.wait()
    observer.stop()
    observer.join()


def run_stream():
    # Reads from transport._stream_queue (transport.py's single input stream)
    # instead of opening a second PyAudio input, which fails on macOS CoreAudio.
    import transport
    transport.run_stream_from_transport()


if __name__ == "__main__":
    print(f"Take — artist session started")
    print(f"  Watching : {WATCH_PATH}")
    print("Press Ctrl+C to stop.\n")

    threads = [
        threading.Thread(target=run_watcher, name="watcher", daemon=True),
        threading.Thread(target=run_stream, name="stream", daemon=True),
    ]
    for t in threads:
        t.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        stop_event.set()
        for t in threads:
            t.join()
        print("Stopped.")
