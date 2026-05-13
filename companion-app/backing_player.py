import os
import time
import threading
import numpy as np
import soundfile as sf
import sounddevice as sd
import timecode as tc

INCOMING_PATH = os.path.join(os.path.dirname(__file__), "incoming")
BACKING_PATH  = os.path.join(INCOMING_PATH, "take_backing_track.mp3")

stop_event = threading.Event()

SYNC_INTERVAL = 0.5   # seconds between drift checks
DRIFT_LIMIT   = 2.0   # seconds before we seek


def run_backing_player():
    while not stop_event.is_set():
        if not os.path.exists(BACKING_PATH):
            time.sleep(1)
            continue

        data, samplerate = sf.read(BACKING_PATH, dtype="float32")
        if data.ndim == 1:
            data = data.reshape(-1, 1)
        total_samples = len(data)
        channels      = data.shape[1]
        print("Backing track loaded — waiting for timecode")

        _play_loop(data, samplerate, total_samples, channels)


def _play_loop(data, samplerate, total_samples, channels):
    while not stop_event.is_set():
        # Wait for Reaper to start playing
        while not stop_event.is_set() and not tc.state["playing"]:
            time.sleep(SYNC_INTERVAL)
        if stop_event.is_set():
            return

        # Seek to current timecode position
        tc_pos     = tc.state["pos"]
        start      = max(0, min(int(tc_pos * samplerate), total_samples - 1))
        pos        = [start]          # mutable so callback can update it
        seek_event = threading.Event()

        def callback(outdata, frames, time_info, status):
            s     = pos[0]
            e     = s + frames
            chunk = data[s : min(e, total_samples)]
            outdata[: len(chunk)] = chunk
            if len(chunk) < frames:
                outdata[len(chunk) :] = 0
            pos[0] = e

        print(f"Backing track — playing from {tc_pos:.1f}s")
        with sd.OutputStream(samplerate=samplerate, channels=channels,
                             dtype="float32", callback=callback):
            while not stop_event.is_set():
                time.sleep(SYNC_INTERVAL)

                if not tc.state["playing"]:
                    print("Backing track — paused")
                    break

                backing_sec = pos[0] / samplerate
                drift       = abs(backing_sec - tc.state["pos"])
                if drift > DRIFT_LIMIT:
                    print(f"Backing track — drift {drift:.1f}s, seeking")
                    break   # stream closes; outer loop restarts at fresh TC pos


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
