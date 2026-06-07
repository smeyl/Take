import socket
import threading
import time
import numpy as np
from pedalboard import Pedalboard, Reverb, Delay, Compressor

DEBUG = False

PORT = 5003
CHUNK = 1024
RATE = 44100

params = {"reverb": 0, "reverbMix": 0, "delay": 0, "delayMix": 0, "compression": 0, "volume": 100}
stop_event = threading.Event()

# Persistent effects — module-level so reverb tail and delay buffer survive between chunks
_compressor = Compressor(threshold_db=0.0, ratio=4.0, attack_ms=10.0, release_ms=100.0)
_reverb     = Reverb(room_size=0.1, wet_level=0.0, dry_level=1.0, damping=0.5, freeze_mode=0.0)
_delay      = Delay(delay_seconds=0.01, feedback=0.3, mix=0.0)
_board      = Pedalboard([_compressor, _reverb, _delay])

def process_audio(samples):
    # Update effect attributes in-place — preserves internal buffer state across chunks
    _compressor.threshold_db = -40.0 + (params["compression"] / 100.0) * 40.0
    _compressor.ratio        = 4.0
    _compressor.attack_ms    = 10.0
    _compressor.release_ms   = 100.0

    _reverb.room_size   = 0.1 + (params["reverb"] / 100.0) * 0.9
    _reverb.wet_level   = params["reverbMix"] / 100.0
    _reverb.dry_level   = 1.0 - params["reverbMix"] / 100.0
    _reverb.damping     = 0.5
    _reverb.freeze_mode = 0.0

    _delay.delay_seconds = max(0.01, params["delay"] / 100.0)
    _delay.feedback      = 0.3
    _delay.mix           = params["delayMix"] / 100.0

    audio_2d  = samples.astype(np.float32) / 32768.0
    audio_2d  = audio_2d.reshape(1, -1)
    processed = _board(audio_2d, sample_rate=RATE, reset=False)  # (1, n_samples) float32
    processed = np.clip(processed, -1.0, 1.0)  # hard limit pedalboard output before volume
    result    = processed[0]
    result   *= params["volume"] / 100.0        # vol_gain: 0.0–1.0, never amplifies above unity
    out = (result * 32767.0).astype(np.int16)

    return out


# ── Network listener ──────────────────────────────────────────────────────────

def listen_for_cues():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", PORT))
    sock.settimeout(1.0)

    while not stop_event.is_set():
        try:
            data, _ = sock.recvfrom(256)
            name, value_str = data.decode().strip().split(":")
            value = int(value_str)
            if name not in params:
                continue
            params[name] = value
            if DEBUG:
                if name == "volume":
                    print(f"  volume     → {value/100:.2f}x", flush=True)
                elif name == "reverb":
                    print(f"  reverb     → room {value/100*0.9:.2f}", flush=True)
                elif name == "reverbMix":
                    print(f"  reverb     → mix {value/100:.2f}", flush=True)
                elif name == "delay":
                    print(f"  delay      → {value/100:.2f}s", flush=True)
                elif name == "delayMix":
                    print(f"  delay      → mix {value/100:.2f}", flush=True)
                elif name == "compression":
                    print(f"  comp       → {value} (unused)", flush=True)
        except socket.timeout:
            continue
        except Exception as e:
            print(f"  cue parse error: {e}", flush=True)

    sock.close()


if __name__ == "__main__":
    print("Take — cue receiver (param listener only)")
    t = threading.Thread(target=listen_for_cues, daemon=True)
    t.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        stop_event.set()
        t.join()
        print("Stopped.")
