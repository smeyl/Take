import socket
import threading

import numpy as np
import pyaudio

import cue_receiver

PORT = 5002
CHUNK = 1024
RATE = 44100
FORMAT = pyaudio.paInt16
CHANNELS = 1
QUALITY_FILE = "/tmp/take_stream_quality"


def _get_quality():
    try:
        with open(QUALITY_FILE) as fh:
            return fh.read().strip()
    except OSError:
        return "AAC256"


def _decode(data):
    q = _get_quality()
    if q == "AAC128":
        return np.frombuffer(data, dtype=np.int16)
    elif q == "AAC256":
        arr = np.frombuffer(data, dtype=np.int32)
        return (arr >> 8).astype(np.int16)
    else:  # FLAC
        arr = np.frombuffer(data, dtype=np.float32)
        return np.clip(arr * 32768.0, -32768, 32767).astype(np.int16)


def run_stream_receiver(stop_event):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", PORT))
    sock.settimeout(1.0)

    audio = pyaudio.PyAudio()
    stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                        output=True, frames_per_buffer=CHUNK)

    try:
        while not stop_event.is_set():
            try:
                data, _ = sock.recvfrom(CHUNK * 4)  # 4 bytes/sample covers int32 and float32
                samples = _decode(data)
                out = cue_receiver.process_audio(samples)
                stream.write(out.tobytes())
            except socket.timeout:
                continue
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()
        sock.close()


if __name__ == "__main__":
    stop = threading.Event()
    try:
        run_stream_receiver(stop)
    except KeyboardInterrupt:
        stop.set()
        print("Stopped.")
