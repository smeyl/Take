import os
import shutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

AUDIO_EXTENSIONS = {".wav", ".mp3", ".aiff", ".aif", ".flac", ".ogg", ".m4a"}
WATCH_PATH = os.path.join(os.path.dirname(__file__), "recordings")
INCOMING_PATH = os.path.join(os.path.dirname(__file__), "incoming")


class AudioHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        _, ext = os.path.splitext(event.src_path)
        if ext.lower() not in AUDIO_EXTENSIONS:
            return
        filename = os.path.basename(event.src_path)
        size = os.path.getsize(event.src_path)
        dest = os.path.join(INCOMING_PATH, filename)
        shutil.copy2(event.src_path, dest)
        print(f"New file: {filename} ({size} bytes) — copied to incoming/")


if __name__ == "__main__":
    os.makedirs(WATCH_PATH, exist_ok=True)
    os.makedirs(INCOMING_PATH, exist_ok=True)
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
