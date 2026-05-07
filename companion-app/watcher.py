import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from sender import send_file

AUDIO_EXTENSIONS = {".wav", ".mp3", ".aiff", ".aif", ".flac", ".ogg", ".m4a"}
WATCH_PATH = os.path.join(os.path.dirname(__file__), "recordings")
TARGET_IP = "127.0.0.1"  # change this to the receiver's IP address


class AudioHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        _, ext = os.path.splitext(event.src_path)
        if ext.lower() not in AUDIO_EXTENSIONS:
            return
        filename = os.path.basename(event.src_path)
        size = os.path.getsize(event.src_path)
        print(f"New file: {filename} ({size} bytes) — sending to {TARGET_IP}...")
        send_file(event.src_path, TARGET_IP)


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
