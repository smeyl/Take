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


def listen_for_cues():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", PORT))
    sock.settimeout(1.0)
    print(f"Listening for cues on UDP port {PORT}")

    while not stop_event.is_set():
        try:
            data, addr = sock.recvfrom(256)
            name, value_str = data.decode().strip().split(":")
            value = int(value_str)
            if name in params:
                params[name] = value
                if name == "volume":
                    print(f"  volume: {value}  (gain → {value / 100:.2f}x)")
                else:
                    print(f"  {name}: {value}  (placeholder)")
        except socket.timeout:
            continue
        except Exception as e:
            print(f"  cue parse error: {e}")

    sock.close()


def run_audio():
    p = pyaudio.PyAudio()
    in_stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                       input=True, frames_per_buffer=CHUNK)
    out_stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                        output=True, frames_per_buffer=CHUNK)
    print("Mic → gain → output running")

    try:
        while not stop_event.is_set():
            raw = in_stream.read(CHUNK, exception_on_overflow=False)
            gain = params["volume"] / 100.0
            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
            samples = np.clip(samples * gain, -32768, 32767).astype(np.int16)
            out_stream.write(samples.tobytes())
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
