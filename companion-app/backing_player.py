import os
import time
import threading
import numpy as np
import soundfile as sf
import sounddevice as sd

INCOMING_PATH = os.path.join(os.path.dirname(__file__), "incoming")
BACKING_PATH = os.path.join(INCOMING_PATH, "take_backing_track.mp3")

stop_event = threading.Event()


def run_backing_player():
    print(f"[debug] backing_player started, polling for {BACKING_PATH}")
    while not stop_event.is_set():
        exists = os.path.exists(BACKING_PATH)
        print(f"[debug] poll: file exists = {exists}")
        if not exists:
            time.sleep(1)
            continue

        print(f"[debug] file detected — reading with soundfile")
        data, samplerate = sf.read(BACKING_PATH, dtype="float32")
        print(f"[debug] loaded: shape={data.shape}, samplerate={samplerate}, dtype={data.dtype}")
        if data.ndim == 1:
            data = data.reshape(-1, 1)

        channels = data.shape[1]
        pos = [0]

        def callback(outdata, frames, time_info, status):
            if status:
                print(f"[debug] stream status: {status}")
            start = pos[0]
            end = start + frames
            if end >= len(data):
                first = data[start:]
                second = data[: end - len(data)]
                outdata[:] = np.concatenate([first, second])
                pos[0] = end - len(data)
            else:
                outdata[:] = data[start:end]
                pos[0] = end

        print(f"[debug] opening OutputStream: samplerate={samplerate}, channels={channels}")
        print("Backing track received - playing")
        with sd.OutputStream(samplerate=samplerate, channels=channels,
                             dtype="float32", callback=callback):
            print("[debug] OutputStream open — playback running")
            while not stop_event.is_set():
                time.sleep(0.1)
        print("[debug] OutputStream closed")


if __name__ == "__main__":
    print(f"Watching for {BACKING_PATH}")
    t = threading.Thread(target=run_backing_player, daemon=True)
    t.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        stop_event.set()
        t.join()
        print("Stopped.")
