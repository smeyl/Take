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
    while not stop_event.is_set():
        if not os.path.exists(BACKING_PATH):
            time.sleep(1)
            continue

        data, samplerate = sf.read(BACKING_PATH, dtype="float32")
        if data.ndim == 1:
            data = data.reshape(-1, 1)

        channels = data.shape[1]
        pos = [0]

        def callback(outdata, frames, time_info, status):
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

        print("Backing track received - playing")
        with sd.OutputStream(samplerate=samplerate, channels=channels,
                             dtype="float32", callback=callback):
            while not stop_event.is_set():
                time.sleep(0.1)


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
