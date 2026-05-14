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
                data, _ = sock.recvfrom(CHUNK * 2)  # 2 bytes per int16 frame
                samples = np.frombuffer(data, dtype=np.int16)
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
