import json
import socket
import requests

PORT = 5005
state = {"pos": 0.0, "playing": False}


def _parse_transport(text):
    """
    Reaper GET /GET/TRANSPORT response: newline-separated values.
    Line 0: playback position in seconds
    Line 1: play state — 0=stopped, 1=playing, 2=paused, 5=recording
    """
    try:
        lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
        pos = float(lines[0])
        playing = len(lines) > 1 and int(float(lines[1])) in (1, 5)
        return pos, playing
    except Exception:
        return 0.0, False


def sender(target_ip, stop_evt):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    while not stop_evt.is_set():
        pos, playing = 0.0, False
        try:
            r = requests.get("http://localhost:8080/GET/TRANSPORT", timeout=0.1)
            if r.ok:
                pos, playing = _parse_transport(r.text)
        except requests.RequestException:
            pass
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
