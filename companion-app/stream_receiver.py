import socket
import pyaudio

PORT = 5002
CHUNK = 1024
RATE = 44100
FORMAT = pyaudio.paInt16
CHANNELS = 1

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", PORT))

audio = pyaudio.PyAudio()
stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                    output=True, frames_per_buffer=CHUNK)

print(f"Listening on UDP port {PORT} — Ctrl+C to stop")
try:
    while True:
        data, _ = sock.recvfrom(CHUNK * 2)  # 2 bytes per frame (16-bit)
        stream.write(data)
except KeyboardInterrupt:
    pass
finally:
    stream.stop_stream()
    stream.close()
    audio.terminate()
    sock.close()
    print("Stopped.")
