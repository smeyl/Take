import socket
import threading

import pyaudio

import stream_sender

PORT = 5008
CHUNK = 1024
RATE = 44100

# Toggled from the JUCE app via transport.py POST /return-stream.
# Packets keep arriving either way; disabled just means we drop them, so
# enabling is instant and never blocks the engineer's sender.
enabled = False


def run_stream_receiver(stop_event):
    """Layer 2: engineer's processed mix, UDP :5008 → its own output stream
    (separate from the cue mix output owned by transport.py)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", PORT))
    sock.settimeout(1.0)

    audio = pyaudio.PyAudio()
    out = None
    print(f"Return stream: UDP 0.0.0.0:{PORT} (engineer mix, toggle in artist app)")
    try:
        while not stop_event.is_set():
            try:
                # Largest packet: 1 header byte + CHUNK samples of float32
                data, _ = sock.recvfrom(CHUNK * 4 + 1)
            except socket.timeout:
                continue
            if not enabled:
                continue
            if out is None:
                try:
                    out = audio.open(format=pyaudio.paInt16, channels=1, rate=RATE,
                                     output=True, frames_per_buffer=CHUNK)
                except Exception as e:
                    print(f"Return stream: output open failed ({e})")
                    enabled_off_wait(stop_event)
                    continue
            try:
                out.write(stream_sender.decode_to_int16(data))
            except OSError:
                pass
    finally:
        if out is not None:
            out.stop_stream()
            out.close()
        audio.terminate()
        sock.close()


def enabled_off_wait(stop_event):
    """Back off after an output-device failure so we don't retry every packet."""
    global enabled
    enabled = False
    stop_event.wait(1.0)


if __name__ == "__main__":
    stop = threading.Event()
    enabled = True
    try:
        run_stream_receiver(stop)
    except KeyboardInterrupt:
        stop.set()
