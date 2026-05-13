import socket
import threading
import time
import numpy as np

PORT = 5003
CHUNK = 1024
RATE = 44100

params = {"reverb": 0, "reverbMix": 0, "delay": 0, "delayMix": 0, "compression": 0, "volume": 100}
stop_event = threading.Event()

# ── Delay line ────────────────────────────────────────────────────────────────
_DELAY_MAX = RATE * 2                    # 2-second circular buffer (88200 samples)
_delay_buf = np.zeros(_DELAY_MAX, dtype=np.float32)
_delay_pos = 0

# ── Reverb (single comb filter, 50 ms) ───────────────────────────────────────
_COMB_DELAY = 2205                       # 50 ms at 44100 Hz; > CHUNK so fully vectorised
_comb_buf   = np.zeros(_COMB_DELAY, dtype=np.float32)
_comb_pos   = 0


def _buf_read(buf, pos, n):
    d   = len(buf)
    pos = int(pos) % d
    end = pos + n
    if end <= d:
        return buf[pos:end].copy()
    split = d - pos
    return np.concatenate([buf[pos:], buf[:n - split]])


def _buf_write(buf, pos, data):
    d   = len(buf)
    pos = int(pos) % d
    n   = len(data)
    end = pos + n
    if end <= d:
        buf[pos:end] = data
    else:
        split = d - pos
        buf[pos:]       = data[:split]
        buf[:n - split] = data[split:]


_call_count = 0


def process_audio(raw_int16):
    global _delay_pos, _comb_pos, _call_count
    _call_count += 1
    if _call_count % 100 == 0:
        print(f"DSP #{_call_count}: rev={params['reverb']} revMix={params['reverbMix']} "
              f"del={params['delay']} delMix={params['delayMix']} vol={params['volume']}", flush=True)

    samples = raw_int16.astype(np.float32) / 32768.0   # → [-1.0, 1.0]

    # Volume
    samples = samples * (params["volume"] / 100.0)

    # Delay — always write to buffer so enabling delay mid-session sounds natural
    delay_samples = int(params["delay"] / 100.0 * RATE)
    delayed = _buf_read(_delay_buf, _delay_pos - delay_samples, len(samples))
    _buf_write(_delay_buf, _delay_pos, samples)
    _delay_pos = (_delay_pos + len(samples)) % _DELAY_MAX
    delay_mix = params["delayMix"] / 100.0
    if delay_mix > 0:
        samples = samples * (1.0 - delay_mix) + delayed * delay_mix

    # Reverb — single comb filter; skip entirely when mix is 0
    reverb_mix = params["reverbMix"] / 100.0
    if reverb_mix > 0:
        feedback = 0.5 + (params["reverb"] / 100.0) * 0.4
        prev     = _buf_read(_comb_buf, _comb_pos, len(samples))
        comb_out = samples + feedback * prev
        _buf_write(_comb_buf, _comb_pos, comb_out)
        _comb_pos = (_comb_pos + len(samples)) % _COMB_DELAY
        samples = samples * (1.0 - reverb_mix) + comb_out * reverb_mix

    return (np.clip(samples, -1.0, 1.0) * 32767.0).astype(np.int16)


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
            if name == "volume":
                print(f"  volume     → {value/100:.2f}x", flush=True)
            elif name == "reverb":
                print(f"  reverb     → size {value}", flush=True)
            elif name == "reverbMix":
                print(f"  reverb     → mix {value/100:.2f}", flush=True)
            elif name == "delay":
                print(f"  delay      → {int(value/100*1000)}ms", flush=True)
            elif name == "delayMix":
                print(f"  delay      → mix {value/100:.2f}", flush=True)
            elif name == "compression":
                print(f"  comp       → {value} (pass-through)", flush=True)
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
