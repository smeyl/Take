import json
import socket
import requests

import daw

PORT = 5005
state = {"pos": 0.0, "playing": False}


def sender(target_ip, stop_evt):
    # Transport state comes from take_session.lua's file export — NOT the
    # Reaper web API, which returns 404 on this setup (see CLAUDE.md).
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    while not stop_evt.is_set():
        pos, playing = daw.get_transport()
        packet = json.dumps({"pos": round(pos, 3), "playing": playing}).encode()
        try:
            sock.sendto(packet, (target_ip, PORT))
        except OSError:
            pass
        try:
            requests.post("http://127.0.0.1:5010/timecode",
                          json={"pos": round(pos, 3), "playing": playing},
                          timeout=0.04)
        except requests.RequestException:
            pass
        stop_evt.wait(0.05)
    sock.close()


def receiver(stop_evt):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", PORT))
    sock.settimeout(1.0)
    while not stop_evt.is_set():
        try:
            data, _ = sock.recvfrom(256)
            parsed = json.loads(data.decode())
            state["pos"]     = float(parsed.get("pos", 0.0))
            state["playing"] = bool(parsed.get("playing", False))
        except socket.timeout:
            continue
        except Exception:
            pass
    sock.close()
