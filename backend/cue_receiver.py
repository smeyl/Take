import socket
import threading
import time
import numpy as np
from pedalboard import Pedalboard, Reverb, Delay, Compressor

PORT = 5003

params = {"reverb": 0, "reverbMix": 0, "delay": 0, "delayMix": 0, "compression": 0, "volume": 100}
stop_event = threading.Event()

# Persistent effects — module-level so reverb tail and delay buffer survive between chunks
_compressor = Compressor(threshold_db=0.0, ratio=4.0, attack_ms=10.0, release_ms=100.0)
_reverb     = Reverb(room_size=0.1, wet_level=0.0, dry_level=1.0, damping=0.5, freeze_mode=0.0)
_delay      = Delay(delay_seconds=0.01, feedback=0.3, mix=0.0)
_board      = Pedalboard([_compressor, _reverb, _delay])

def process(block, sample_rate):
    """Run one block of mono float32 audio through the cue mix and return it.
    Called from the artist's output audio callback, at the device's native
    rate, a few ms of audio at a time."""
    # Update effect attributes in-place — preserves internal buffer state across chunks
    # 0 = off (threshold at full scale, nothing is compressed), like every
    # other cue knob at 0; 100 = heaviest (-40 dB threshold).
    _compressor.threshold_db = -40.0 * (params["compression"] / 100.0)
    _compressor.ratio        = 4.0
    _compressor.attack_ms    = 10.0
    _compressor.release_ms   = 100.0

    # JUCE's reverb (under pedalboard) multiplies dry_level by 2, so dry is
    # halved here: 0% mix is then unity gain, not +6 dB. Its wet side comes
    # out near unity at wet_level 1.0 (measured with noise), so 100% mix is
    # about as loud as the dry signal and the knob crossfades between them.
    _reverb.room_size   = 0.1 + (params["reverb"] / 100.0) * 0.9
    _reverb.wet_level   = params["reverbMix"] / 100.0
    _reverb.dry_level   = (1.0 - params["reverbMix"] / 100.0) / 2.0
    _reverb.damping     = 0.5
    _reverb.freeze_mode = 0.0

    _delay.delay_seconds = max(0.01, params["delay"] / 100.0)
    _delay.feedback      = 0.3
    _delay.mix           = params["delayMix"] / 100.0

    processed = _board(block.reshape(1, -1), sample_rate=sample_rate, reset=False)
    processed = np.clip(processed[0], -1.0, 1.0)  # hard limit pedalboard output before volume
    return processed * (params["volume"] / 100.0)  # 0.0–1.0, never amplifies above unity


# ── Network listener ──────────────────────────────────────────────────────────

def listen_for_cues():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(("0.0.0.0", PORT))
    except OSError:
        # Without this listener the engineer's knob changes never arrive —
        # don't let that die silently on a background thread.
        print(f"FATAL: cue receiver could not bind UDP {PORT} — another "
              f"process owns it (lsof -i :{PORT}). Engineer cue changes "
              f"will NOT reach the artist DSP.", flush=True)
        return
    sock.settimeout(1.0)

    while not stop_event.is_set():
        try:
            data, _ = sock.recvfrom(256)
            name, value_str = data.decode().strip().split(":")
            value = int(value_str)
            if name not in params:
                continue
            params[name] = value
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
