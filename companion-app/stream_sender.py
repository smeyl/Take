import sys
import socket
import pyaudio

HOST = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
PORT = 5002
CHUNK = 1024
RATE = 44100
FORMAT = pyaudio.paInt16
CHANNELS = 1

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
audio = pyaudio.PyAudio()

stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                    input=True, frames_per_buffer=CHUNK)

print(f"Streaming microphone to {HOST}:{PORT} — Ctrl+C to stop")
try:
    while True:
        data = stream.read(CHUNK, exception_on_overflow=False)
        sock.sendto(data, (HOST, PORT))
except KeyboardInterrupt:
    pass
finally:
    stream.stop_stream()
    stream.close()
    audio.terminate()
    sock.close()
    print("Stopped.")
