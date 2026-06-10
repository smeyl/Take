import socket
import threading

import pyaudio

import stream_sender

RETURN_PORT = 5008
CHUNK = 1024
RATE = 44100


def _find_loopback_input(audio):
    """Prefer a second BlackHole device (e.g. 16ch) so the return feed doesn't
    collide with the 2ch device Reaper already uses for the artist's mic."""
    candidates = []
    for i in range(audio.get_device_count()):
        info = audio.get_device_info_by_index(i)
        name = info.get("name", "")
        if "BlackHole" in name and info.get("maxInputChannels", 0) > 0:
            candidates.append((i, name))
    if not candidates:
        return None, None
    for i, name in candidates:
        if "2ch" not in name:
            return i, name
    return candidates[0]


def run_return_sender(target_ip, stop_event):
    """Layer 2: stream the engineer's processed mix to the artist (UDP :5008).

    Route Reaper's master (or a multi-output device) into BlackHole on this
    machine; whatever lands there is captured here and sent to the artist.
    """
    audio = pyaudio.PyAudio()
    idx, name = _find_loopback_input(audio)
    if idx is None:
        print("Return stream: no BlackHole input device — engineer mix not sent")
        audio.terminate()
        return
    try:
        stream = audio.open(format=pyaudio.paInt16, channels=1, rate=RATE,
                            input=True, input_device_index=idx,
                            frames_per_buffer=CHUNK)
    except Exception as e:
        print(f"Return stream: could not open {name} ({e})")
        audio.terminate()
        return

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"Return stream: {name} → {target_ip}:{RETURN_PORT}")
    try:
        while not stop_event.is_set():
            data = stream.read(CHUNK, exception_on_overflow=False)
            sock.sendto(stream_sender.FMT_INT16 + data, (target_ip, RETURN_PORT))
    except OSError:
        pass
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()
        sock.close()


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    stop = threading.Event()
    try:
        run_return_sender(target, stop)
    except KeyboardInterrupt:
        stop.set()
