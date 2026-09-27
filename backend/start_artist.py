import ipv4  # noqa: F401 — IPv4-only HTTP lookups (NAT64 networks); must come first
import json
import os
import signal
import socket
import sys
import time
import threading
import requests
from urllib.parse import urlparse

# The relay runs on the engineer's machine: its host comes from each join the
# artist app writes to the session file, or TAKE_RELAY_HOST — see join().
RELAY_PORT = 5010

import ports
import watcher
import artist
import backing_player
import cue_receiver
import loop_latency
import receiver
import stream_sender
import timecode
import transport
from artist import run_watcher, run_stream, stop_event
from backing_player import run_backing_player, BACKING_PATH
from cue_receiver import listen_for_cues
from watcher import WATCH_PATH

STREAM_PORT = 5002
FILE_PORT = 5001
SESSION_FILE = "/tmp/take_session.json"


def get_local_ip():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]


# The session this backend serves: the one the artist app joined last. The
# app writes SESSION_FILE on every join, and this backend follows it — a
# rejoin (after End Session, or to a new code) switches everything over, and
# the timing figures from the previous session are dropped with it.
session = {"code": None, "relay_url": None}
_session_lock = threading.Lock()


def _take_session_file():
    """(engineer_ip, code) from a join the artist app has just written to
    SESSION_FILE, consuming it; None if there isn't one. Ignores the copy this
    backend writes back for the app (its "from" is "backend") and joins over
    a minute old."""
    try:
        with open(SESSION_FILE) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if data.get("from") == "backend":
        return None
    try:
        os.unlink(SESSION_FILE)
    except OSError:
        pass
    written_at_ms = data.get("written_at", 0)
    age_s = (time.time() * 1000 - written_at_ms) / 1000
    if written_at_ms and age_s > 60:
        print(f"Ignoring stale session file (age {age_s:.0f}s)", flush=True)
        return None
    ip, code = data.get("engineer_ip", ""), data.get("code", "")
    return (ip, code) if ip and code else None


def _wait_for_session_file():
    """Wait — however long it takes — for the artist app to join a session.
    Joining can take a while (finding the code, typing the engineer's address
    by hand), and the backend is no use until it happens."""
    waited = 0
    while not stop_event.is_set():
        joined = _take_session_file()
        if joined:
            return joined
        stop_event.wait(1)
        waited += 1
        if waited % 60 == 0:
            print(f"Still waiting for the artist app to join a session "
                  f"({waited // 60} min)...", flush=True)
    return None


def join(ip, code):
    """Join session `code` on the relay at `ip` and point everything at its
    engineer. Returns True once joined; False if the relay can't be reached
    within a minute or the session doesn't exist."""
    # The relay lives on the engineer's machine: TAKE_RELAY_HOST if set,
    # otherwise the engineer IP the artist app joined with.
    relay_url = f"http://{os.environ.get('TAKE_RELAY_HOST') or ip}:{RELAY_PORT}"
    print(f"Joining session {code} — relay {relay_url}", flush=True)
    deadline = time.time() + 60
    while True:
        try:
            resp = requests.post(f"{relay_url}/session/join",
                                 json={"code": code, "ip": get_local_ip()}, timeout=5)
            if resp.status_code == 404:
                print(f"Session {code} doesn't exist (any more) — waiting for the "
                      f"artist app to join another", flush=True)
                return False
            resp.raise_for_status()
            break
        except requests.RequestException:
            if time.time() > deadline or stop_event.is_set():
                print("Could not reach the engineer's relay for a minute — waiting "
                      "for the artist app to join again", flush=True)
                return False
            print("Waiting for engineer...", flush=True)
            stop_event.wait(3)
    engineer_ip = resp.json()["engineer_ip"]
    with _session_lock:
        session.update(code=code, relay_url=relay_url)
        # Figures from any previous session (another path, another engineer)
        # would misplace the backing track; the heartbeat refills them.
        loop_latency.reset()
        watcher.TARGET_IP = engineer_ip
        artist.TARGET_IP = engineer_ip
        transport.RELAY_URL = relay_url  # Reaper record/stop commands route through the relay
        transport.STREAM_TO = engineer_ip
    # Tell the artist app the engineer's address (it pre-fills the manual
    # address field from this); marked as ours so it isn't taken as a join.
    with open(SESSION_FILE, "w") as f:
        json.dump({"engineer_ip": engineer_ip, "code": code, "from": "backend",
                   "written_at": int(time.time() * 1000)}, f)
    print(f"Engineer found — {engineer_ip}\n"
          f"  File transfer   : {engineer_ip}:{FILE_PORT}\n"
          f"  Mic stream out  : {engineer_ip}:{STREAM_PORT}", flush=True)
    return True


def _drop_session(reason, waiting=True):
    """Stop serving the current session (it's over, or the artist left): no
    more heartbeats or mic stream, and its timing figures are forgotten."""
    with _session_lock:
        code, relay_url = session["code"], session["relay_url"]
        session.update(code=None, relay_url=None)
        transport.STREAM_TO = None
        loop_latency.reset()
    if code:
        print(f"{reason} — waiting for the artist app to join again" if waiting else reason,
              flush=True)
    return code, relay_url


def leave(waiting=True):
    """The artist app's End Session: only this side disconnects. The session
    stays open on the relay — ending it is the engineer's action."""
    code, relay_url = _drop_session("Left the session", waiting)
    if code:
        try:
            requests.post(f"{relay_url}/session/{code}/leave", timeout=3)
        except requests.RequestException:
            pass


def run_session(stop_evt):
    """Heartbeat the session being served, and follow the artist app to a new
    one whenever it joins again."""
    engineer_was_alive = None
    next_heartbeat = 0.0
    while not stop_evt.is_set():
        joined = _take_session_file()
        if joined and join(*joined):
            engineer_was_alive = None
            next_heartbeat = 0.0
        code, relay_url = session["code"], session["relay_url"]
        if code and time.monotonic() >= next_heartbeat:
            next_heartbeat = time.monotonic() + 5
            engineer_was_alive = _heartbeat(relay_url, code, engineer_was_alive)
        stop_evt.wait(1)


def _heartbeat(relay_url, code, engineer_was_alive):
    # Time a TCP connect to the relay — one network round trip — for the
    # backing-track advance (loop_latency.py).
    relay = urlparse(relay_url)
    try:
        t = time.perf_counter()
        socket.create_connection((relay.hostname, relay.port), timeout=3).close()
        rtt = time.perf_counter() - t
    except OSError:
        rtt = None
    try:
        requests.post(f"{relay_url}/session/{code}/heartbeat",
                      json={"role": "artist"}, timeout=3)
        r = requests.get(f"{relay_url}/session/{code}/status", timeout=3)
    except requests.RequestException:
        return engineer_was_alive
    # A 404: the engineer ended the session (or replaced it with a new code).
    ended = r.status_code == 404
    with _session_lock:
        if session["code"] != code:
            return None   # switched sessions meanwhile — these figures aren't its
        if not ended:
            if rtt is not None:
                loop_latency.add_rtt(rtt)
            if r.ok:
                loop_latency.update_engineer(r.json().get("latency"))
    if ended:
        _drop_session(f"Session {code} was ended by the engineer")
        return None
    if not r.ok:
        return engineer_was_alive
    engineer_alive = r.json()["engineer"]
    if engineer_alive and engineer_was_alive is False:
        print("✓ Engineer reconnected", flush=True)
    elif not engineer_alive and engineer_was_alive:
        print("⚠ Engineer disconnected — waiting for them to come back", flush=True)
    return engineer_alive


def run_file_receiver():
    """Receives the engineer's bounced backing track on port 5009.
    Distinct from the engineer's take receiver (5001) so the two can coexist
    on one machine — takes always reach the engineer's process."""
    try:
        receiver.app.run(host="0.0.0.0", port=receiver.ARTIST_PORT, use_reloader=False)
    except OSError:
        print(f"FATAL: file receiver could not bind port {receiver.ARTIST_PORT} — "
              f"another process owns it (lsof -i :{receiver.ARTIST_PORT}). "
              f"Backing tracks will NOT arrive.", flush=True)


if __name__ == "__main__":
    ports.ensure_free([
        (transport.PORT,            "tcp", "transport"),
        (stream_sender.FLASK_PORT,  "tcp", "stream quality"),
        (receiver.ARTIST_PORT,      "tcp", "file receiver (backing track)"),
        (cue_receiver.PORT,         "udp", "cue params"),
        (timecode.PORT,             "udp", "timecode"),
    ])

    transport.on_leave = leave
    print("Waiting for the artist app to join a session...", flush=True)
    while True:
        joined = _wait_for_session_file()
        if joined is None:
            sys.exit(0)
        if join(*joined):
            break

    shutdown_reason = [None]

    def shutdown(reason=None):
        if stop_event.is_set():
            return
        shutdown_reason[0] = reason
        stop_event.set()
        backing_player.stop_event.set()
        cue_receiver.stop_event.set()

    signal.signal(signal.SIGINT, lambda sig, frame: shutdown())
    signal.signal(signal.SIGTERM, lambda sig, frame: shutdown())
    # Closing the Terminal window it runs in (Take Artist.app) — leave cleanly.
    signal.signal(signal.SIGHUP, lambda sig, frame: shutdown())

    threads = [
        threading.Thread(target=run_watcher, name="watcher", daemon=True),
        threading.Thread(target=run_stream, name="stream", daemon=True),
        threading.Thread(target=run_backing_player, name="backing-player", daemon=True),
        threading.Thread(target=listen_for_cues, name="cue-receiver", daemon=True),
        threading.Thread(
            target=transport.app.run,
            kwargs={"host": "0.0.0.0", "port": transport.PORT, "use_reloader": False},
            name="transport",
            daemon=True,
        ),
        threading.Thread(
            target=stream_sender.run_flask,
            name="stream-quality",
            daemon=True,
        ),
        threading.Thread(target=run_file_receiver, name="file-receiver", daemon=True),
        threading.Thread(target=run_session, args=(stop_event,),
                         name="session", daemon=True),
        threading.Thread(target=timecode.receiver, args=(stop_event,),
                         name="timecode", daemon=True),
    ]
    for t in threads:
        t.start()

    print("Take — artist ready")
    print(f"  Watching        : {WATCH_PATH}")
    print(f"  Cue params      : UDP 0.0.0.0:{cue_receiver.PORT}")
    print(f"  Backing player  : {BACKING_PATH}")
    print(f"  Transport       : 0.0.0.0:{transport.PORT}")
    print(f"  Timecode        : UDP 0.0.0.0:{timecode.PORT}")
    print(f"  Stream quality  : 0.0.0.0:{stream_sender.FLASK_PORT}")
    print(f"  File receiver   : 0.0.0.0:{receiver.ARTIST_PORT} → backing track")
    print("Press Ctrl+C to stop.\n")

    stop_event.wait()

    msg = shutdown_reason[0] or "Shutting down..."
    print(f"\n{msg}", flush=True)

    # Only this side leaves: the session is the engineer's to end.
    leave(waiting=False)

    for t in threads:
        t.join(timeout=2)

    sys.exit(0)
