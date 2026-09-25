import json
import socket
import time
import requests

import daw

PORT = 5005
# cursor: the engineer's cursor / selection position in the DAW (seconds),
# mirrored live on the artist's backing track; None when not reported.
state = {"pos": 0.0, "playing": False, "cursor": None}
# (pos, playing, time.monotonic() when received) — replaced as one tuple so
# position_at() never mixes an old packet's time with a new one's position.
_fix = (0.0, False, 0.0)

SEND_INTERVAL = 0.05  # seconds between timecode packets
# While stopped, look for the start every 10 ms (a transport read takes ~4 ms
# on Pro Tools): the DAW's start is only known to within one poll, and that
# uncertainty is the part of the artist's backing-track timing nothing
# downstream can correct. A start is sent at once, not at the next tick.
POLL_STOPPED = 0.01


def position_at(t):
    """Engineer's timecode position (s) at time.monotonic() time `t`,
    extrapolated from the latest packet while playing."""
    pos, playing, received = _fix
    return pos + (t - received) if playing else pos


def sender(target_ip, stop_evt):
    # Transport state comes from take_session.lua's file export — NOT the
    # Reaper web API, which returns 404 on this setup (see CLAUDE.md).
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    last_sent, was_playing = 0.0, None
    while not stop_evt.is_set():
        pos, playing = daw.get_transport()
        now = time.monotonic()
        if playing != was_playing or now - last_sent >= SEND_INTERVAL:
            cursor = daw.get_cursor()
            packet = json.dumps({"pos": round(pos, 4), "playing": playing,
                                 "cursor": None if cursor is None else round(cursor, 3)}).encode()
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
            last_sent, was_playing = now, playing
        stop_evt.wait(SEND_INTERVAL if playing else POLL_STOPPED)
    sock.close()


def receiver(stop_evt):
    global _fix
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", PORT))
    sock.settimeout(1.0)
    while not stop_evt.is_set():
        try:
            data, _ = sock.recvfrom(256)
            received = time.monotonic()
            parsed = json.loads(data.decode())
            state["pos"]     = float(parsed.get("pos", 0.0))
            state["playing"] = bool(parsed.get("playing", False))
            cursor = parsed.get("cursor")
            state["cursor"] = None if cursor is None else float(cursor)
            _fix = (state["pos"], state["playing"], received)
        except socket.timeout:
            continue
        except Exception:
            pass
    sock.close()
