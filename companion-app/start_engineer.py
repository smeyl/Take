import curses
import socket
import threading
import time
import requests
import pyaudio

import engineer  # wires up receiver.on_file_received as a side effect
import cue_sender
from engineer import run_receiver, INCOMING_PATH, PORT, ACTION_INSERT_MEDIA
from reaper import BASE

STREAM_PORT = 5002
CHUNK = 1024
RATE = 44100
FORMAT = pyaudio.paInt16
CHANNELS = 1

stop_event = threading.Event()


def check_reaper():
    try:
        requests.get(BASE, timeout=3)
        return True
    except requests.ConnectionError:
        return False


def run_stream_receiver():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", STREAM_PORT))
    sock.settimeout(1.0)
    audio = pyaudio.PyAudio()
    stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                        output=True, frames_per_buffer=CHUNK)
    try:
        while not stop_event.is_set():
            try:
                data, _ = sock.recvfrom(CHUNK * 2)
                stream.write(data)
            except socket.timeout:
                continue
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()
        sock.close()


if __name__ == "__main__":
    reaper_ok = check_reaper()

    threads = [
        threading.Thread(target=run_receiver, name="http-receiver", daemon=True),
        threading.Thread(target=run_stream_receiver, name="stream-receiver", daemon=True),
    ]
    for t in threads:
        t.start()

    print("Take — engineer ready")
    print(f"  File receiver  : 0.0.0.0:{PORT} → {INCOMING_PATH}/")
    print(f"  Stream receiver: UDP 0.0.0.0:{STREAM_PORT}")
    print(f"  Reaper         : {BASE} ({'reachable' if reaper_ok else 'NOT REACHABLE'})")
    print(f"  Script         : {ACTION_INSERT_MEDIA}")
    print(f"  Cue mix sender : UDP → {cue_sender.TARGET_IP}:{cue_sender.PORT}")
    print("Press Ctrl+C to stop.\n")

    cue_thread = threading.Thread(target=curses.wrapper, args=(cue_sender.main,),
                                  name="cue-sender", daemon=True)
    cue_thread.start()
    threads.append(cue_thread)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        stop_event.set()
        for t in threads:
            t.join()
        print("Stopped.")
