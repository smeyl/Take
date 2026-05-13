import socket
import threading
import time
import numpy as np
import pyaudio

PORT = 5003
CHUNK = 1024
RATE = 44100
FORMAT = pyaudio.paInt16
CHANNELS = 1

params = {"reverb": 0, "delay": 0, "compression": 0, "volume": 100}
stop_event = threading.Event()

# ── Delay ─────────────────────────────────────────────────────────────────────
_DELAY_BUF_SIZE = RATE * 2  # 2 s = 88200 samples
_delay_buf = np.zeros(_DELAY_BUF_SIZE, dtype=np.float32)
_delay_pos = 0

# ── Reverb (Schroeder) ────────────────────────────────────────────────────────
# All comb delays > CHUNK (1024) → fully vectorised.
# All allpass delays < CHUNK → per-sample loop.
_COMB_DELAYS = [1557, 1617, 1491, 1422]
_AP_DELAYS   = [225, 556]
_AP_G        = 0.5
_comb_bufs   = [np.zeros(d, dtype=np.float32) for d in _COMB_DELAYS]
_comb_pos    = [0, 0, 0, 0]
_ap_bufs     = [np.zeros(d, dtype=np.float32) for d in _AP_DELAYS]
_ap_pos      = [0, 0]

# ── Compressor ────────────────────────────────────────────────────────────────
_comp_env   = 0.0
_ATTACK     = np.exp(-1.0 / (0.010 * RATE))   # 10 ms
_RELEASE    = np.exp(-1.0 / (0.100 * RATE))   # 100 ms
_COMP_RATIO = 4.0


# ── Buffer helpers ────────────────────────────────────────────────────────────

def _buf_read(buf, pos, n):
    d = len(buf)
    pos = int(pos) % d
    end = pos + n
    if end <= d:
        return buf[pos:end].copy()
    split = d - pos
    return np.concatenate([buf[pos:], buf[:n - split]])


def _buf_write(buf, pos, data):
    d = len(buf)
    pos = int(pos) % d
    n = len(data)
    end = pos + n
    if end <= d:
        buf[pos:end] = data
    else:
        split = d - pos
        buf[pos:]        = data[:split]
        buf[:n - split]  = data[split:]


# ── DSP stages ────────────────────────────────────────────────────────────────

def _apply_compression(samples, comp_param):
    global _comp_env
    if comp_param == 0:
        return samples
    threshold_lin = 10.0 ** (-40.0 * comp_param / 100.0 / 20.0)
    exp_val       = (_COMP_RATIO - 1.0) / _COMP_RATIO
    attack        = _ATTACK
    release       = _RELEASE
    env           = _comp_env
    out           = samples.copy()
    for i in range(len(samples)):
        level    = abs(samples[i])
        coef     = attack if level > env else release
        env      = coef * env + (1.0 - coef) * level
        if env > threshold_lin:
            out[i] = samples[i] * (threshold_lin / env) ** exp_val
    _comp_env = env
    return out


def _apply_reverb(samples, reverb_param):
    global _comb_pos, _ap_pos
    if reverb_param == 0:
        return samples
    feedback = 0.5 + (reverb_param / 100.0) * 0.4   # 0.5 → 0.9
    mix      = reverb_param / 100.0

    # Four comb filters in parallel
    wet = np.zeros_like(samples)
    for i, (d, buf) in enumerate(zip(_COMB_DELAYS, _comb_bufs)):
        prev     = _buf_read(buf, _comb_pos[i], len(samples))
        comb_out = samples + feedback * prev
        _buf_write(buf, _comb_pos[i], comb_out)
        _comb_pos[i] = (_comb_pos[i] + len(samples)) % d
        wet += comb_out
    wet /= 4.0

    # Two allpass filters in series
    g = _AP_G
    for i, (d, buf) in enumerate(zip(_AP_DELAYS, _ap_bufs)):
        out = np.empty_like(wet)
        pos = _ap_pos[i]
        for n in range(len(wet)):
            idx      = (pos + n) % d
            prev_v   = buf[idx]
            v        = wet[n] + g * prev_v
            out[n]   = prev_v - g * v
            buf[idx] = v
        _ap_pos[i] = (pos + len(wet)) % d
        wet = out

    return samples * (1.0 - mix) + wet * mix


def _apply_delay(samples, delay_param):
    global _delay_pos
    n             = len(samples)
    delay_samples = int((delay_param / 100.0) * RATE)  # 0 → 44100
    mix           = delay_param / 100.0

    if mix > 0:
        delayed = _buf_read(_delay_buf, _delay_pos - delay_samples, n)

    _buf_write(_delay_buf, _delay_pos, samples)
    _delay_pos = (_delay_pos + n) % _DELAY_BUF_SIZE

    if mix == 0:
        return samples
    return samples * (1.0 - mix) + delayed * mix


def process_audio(raw_int16):
    samples = raw_int16.astype(np.float32) / 32768.0   # → [-1, 1]
    samples = _apply_compression(samples, params["compression"])
    samples = _apply_reverb(samples, params["reverb"])
    samples = _apply_delay(samples, params["delay"])
    samples *= params["volume"] / 100.0
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
                print(f"  volume → {value/100:.2f}x gain")
            elif name == "delay":
                ms  = int(value / 100 * 1000)
                mix = value / 100
                print(f"  delay  → {ms}ms / mix {mix:.2f}")
            elif name == "reverb":
                fb  = 0.5 + (value / 100) * 0.4
                mix = value / 100
                print(f"  reverb → feedback {fb:.2f} / mix {mix:.2f}")
            elif name == "compression":
                db = -40.0 * value / 100
                print(f"  comp   → threshold {db:.0f}dB")
        except socket.timeout:
            continue
        except Exception as e:
            print(f"  cue parse error: {e}")

    sock.close()


# ── Audio loop ────────────────────────────────────────────────────────────────

def run_audio():
    p          = pyaudio.PyAudio()
    in_stream  = p.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                        input=True, frames_per_buffer=CHUNK)
    out_stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                        output=True, frames_per_buffer=CHUNK)
    print("Mic → DSP chain → output running")

    try:
        while not stop_event.is_set():
            raw     = in_stream.read(CHUNK, exception_on_overflow=False)
            samples = np.frombuffer(raw, dtype=np.int16)
            out     = process_audio(samples)
            out_stream.write(out.tobytes())
    finally:
        in_stream.stop_stream()
        in_stream.close()
        out_stream.stop_stream()
        out_stream.close()
        p.terminate()


if __name__ == "__main__":
    print("Take — cue receiver")
    threads = [
        threading.Thread(target=listen_for_cues, daemon=True),
        threading.Thread(target=run_audio, daemon=True),
    ]
    for t in threads:
        t.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        stop_event.set()
        for t in threads:
            t.join()
        print("Stopped.")
