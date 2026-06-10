import os
import threading
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from sender import send_file

AUDIO_EXTENSIONS = {".wav", ".mp3", ".aiff", ".aif", ".flac", ".ogg", ".m4a"}
WATCH_PATH = os.path.join(os.path.dirname(__file__), "recordings")
TARGET_IP = "127.0.0.1"


class AudioHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        _, ext = os.path.splitext(event.src_path)
        if ext.lower() not in AUDIO_EXTENSIONS:
            return
        # Spawn a thread to wait until the file is fully written before sending.
        # on_created fires when soundfile creates the empty file; we must wait
        # for recording to stop and the file to be closed and flushed.
        threading.Thread(target=self._wait_and_send, args=(event.src_path,), daemon=True).start()

    def _wait_and_send(self, path):
        prev_size = -1
        stable_count = 0
        while stable_count < 3:
            time.sleep(1)
            try:
                size = os.path.getsize(path)
            except OSError:
                return
            if size > 0 and size == prev_size:
                stable_count += 1
            else:
                stable_count = 0
                prev_size = size
        filename = os.path.basename(path)
        print(f"File ready: {filename} ({prev_size} bytes) — sending to {TARGET_IP}...")
        send_file(path, TARGET_IP)


if __name__ == "__main__":
    os.makedirs(WATCH_PATH, exist_ok=True)
    print(f"Watching {WATCH_PATH} for new audio files...")
    observer = Observer()
    observer.schedule(AudioHandler(), WATCH_PATH, recursive=False)
    observer.start()
    try:
        while observer.is_alive():
            observer.join(timeout=1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
