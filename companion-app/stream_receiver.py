import socket
import threading

PORT = 5002
CHUNK = 1024


def run_stream_receiver(stop_event):
    """Receives the engineer's return stream. Audio output is handled by transport.py directly."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", PORT))
    sock.settimeout(1.0)
    print(f"Stream receiver: UDP 0.0.0.0:{PORT} (engineer return stream)")
    try:
        while not stop_event.is_set():
            try:
                sock.recvfrom(CHUNK * 4)
            except socket.timeout:
                continue
    finally:
        sock.close()


if __name__ == "__main__":
    stop = threading.Event()
    try:
        run_stream_receiver(stop)
    except KeyboardInterrupt:
        stop.set()
        print("Stopped.")
