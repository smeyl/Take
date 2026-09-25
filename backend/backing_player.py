import os
import time
import threading
import numpy as np
import soundfile as sf
import sounddevice as sd
import loop_latency
import timecode as tc

# Data lives at the repo root (sibling of this backend/ folder), not inside it.
INCOMING_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "incoming")
BACKING_PATH  = os.path.join(INCOMING_PATH, "take_backing_track.mp3")

stop_event = threading.Event()

# Duration (seconds) of the currently loaded backing track, 0.0 when none is
# loaded. Exposed via transport.py's /status so the artist app's ruler reflects
# the real track length instead of a fixed guess.
duration = 0.0

# (host time the latest block reaches the output, its track position in
# samples, sample rate) — set by the playback callback, None when not playing.
# Host time is PortAudio's stream clock, shared with transport.py's input
# callback, so heard_position() can map a capture timestamp onto the track.
_anchor = None

# Pro Tools' MP3 export starts with the encoder's lead-in (1230 samples at
# 44.1 kHz, 256 kbps CBR, measured against the session with Pro Tools 2026.4.1)
# and writes no LAME/Info tag telling the decoder to skip it. Trimmed after
# decoding so the track's time 0 is the session's time 0 — without it the
# artist hears everything 28 ms late and takes are placed 28 ms late.
MP3_LEAD_IN = 0.0279  # seconds

START_POLL    = 0.02  # seconds between checks for the timecode starting
SYNC_INTERVAL = 0.5   # seconds between drift checks
DRIFT_LIMIT   = 2.0   # seconds before we seek


def heard_position(host_time):
    """Track position (seconds) the artist heard at `host_time` (PortAudio
    stream time), or None if the backing track isn't playing."""
    a = _anchor
    if a is None:
        return None
    dac, pos, sr = a
    if abs(host_time - dac) > 1.0:   # stale anchor: playback stalled or stopped
        return None
    return (pos + (host_time - dac) * sr) / sr


def _file_changed(loaded_mtime):
    try:
        return os.path.getmtime(BACKING_PATH) != loaded_mtime
    except OSError:
        return False


def run_backing_player():
    global duration
    while not stop_event.is_set():
        if not os.path.exists(BACKING_PATH):
            duration = 0.0
            time.sleep(1)
            continue

        try:
            loaded_mtime = os.path.getmtime(BACKING_PATH)
            data, samplerate = sf.read(BACKING_PATH, dtype="float32")
        except Exception as e:
            # File may still be mid-upload — retry shortly
            print(f"Backing track read failed ({e}) — retrying")
            time.sleep(1)
            continue
        if data.ndim == 1:
            data = data.reshape(-1, 1)
        if BACKING_PATH.endswith(".mp3"):
            data = data[round(MP3_LEAD_IN * samplerate):]
        total_samples = len(data)
        channels      = data.shape[1]
        duration      = total_samples / float(samplerate) if samplerate else 0.0
        print(f"Backing track loaded ({duration:.1f}s) — waiting for timecode")

        _play_loop(data, samplerate, total_samples, channels, loaded_mtime)


def _play_loop(data, samplerate, total_samples, channels, loaded_mtime):
    global _anchor
    while not stop_event.is_set():
        # Wait for the DAW to start playing
        while not stop_event.is_set() and not tc.state["playing"]:
            if _file_changed(loaded_mtime):
                print("Backing track updated — reloading")
                time.sleep(0.5)  # let the upload finish
                return
            time.sleep(START_POLL)
        if stop_event.is_set():
            return

        # Play ahead of the timecode by the loop latency, so the artist's
        # live vocal reaches the DAW in time with it. Fixed for this pass.
        advance, terms = loop_latency.advance()
        pos = [None]                  # track position (samples); set by the first callback

        def callback(outdata, frames, time_info, status):
            global _anchor
            if pos[0] is None:
                # Start where the timecode will be when this first block
                # reaches the output, plus the advance — so neither the
                # timecode packet's age nor the time taken to open this
                # stream makes the track late.
                dac = time.monotonic() + (time_info.outputBufferDacTime - time_info.currentTime)
                pos[0] = max(0, round((tc.position_at(dac) + advance) * samplerate))
            s     = pos[0]
            _anchor = (time_info.outputBufferDacTime, s, samplerate)
            e     = s + frames
            chunk = data[s : min(e, total_samples)]
            outdata[: len(chunk)] = chunk
            if len(chunk) < frames:
                outdata[len(chunk) :] = 0
            pos[0] = e

        with sd.OutputStream(samplerate=samplerate, channels=channels,
                             dtype="float32", callback=callback):
            while pos[0] is None and not stop_event.is_set():
                time.sleep(0.005)
            print(f"Backing track — playing from {pos[0] / samplerate:.3f}s, "
                  f"{advance * 1000:.1f} ms ahead of the timecode {terms}", flush=True)
            while not stop_event.is_set():
                time.sleep(SYNC_INTERVAL)

                if not tc.state["playing"]:
                    print("Backing track — paused")
                    break

                if _file_changed(loaded_mtime):
                    print("Backing track updated — reloading")
                    time.sleep(0.5)  # let the upload finish
                    return

                # Only for seeks and loops the timecode can't follow — the
                # advance itself is never adjusted mid-playback.
                expected = tc.position_at(time.monotonic()) + advance
                drift    = abs(pos[0] / samplerate - expected)
                if drift > DRIFT_LIMIT:
                    print(f"Backing track — drift {drift:.1f}s, seeking")
                    break   # stream closes; outer loop restarts at fresh TC pos
        _anchor = None


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
