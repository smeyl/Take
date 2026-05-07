import os
import socket
import threading
import time
import numpy as np
import pyaudio
from watchdog.observers import Observer
from watcher import AudioHandler, WATCH_PATH, TARGET_IP

STREAM_PORT = 5002
CHUNK = 1024
RATE = 44100
FORMAT = pyaudio.paInt16
CHANNELS = 1

stop_event = threading.Event()


def run_watcher():
    os.makedirs(WATCH_PATH, exist_ok=True)
    observer = Observer()
    observer.schedule(AudioHandler(), WATCH_PATH, recursive=False)
    observer.start()
    stop_event.wait()
    observer.stop()
    observer.join()


def run_stream(params=None):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    audio = pyaudio.PyAudio()
    stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                        input=True, frames_per_buffer=CHUNK)
    try:
        while not stop_event.is_set():
            data = stream.read(CHUNK, exception_on_overflow=False)
            if params is not None:
                gain = params["volume"] / 100.0
                samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
                data = np.clip(samples * gain, -32768, 32767).astype(np.int16).tobytes()
            sock.sendto(data, (TARGET_IP, STREAM_PORT))
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()
        sock.close()


if __name__ == "__main__":
    print(f"Take — artist session started")
    print(f"  Watching : {WATCH_PATH}")
    print(f"  Streaming : {TARGET_IP}:{STREAM_PORT}")
    print(f"  Transfers : {TARGET_IP}:5001")
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
