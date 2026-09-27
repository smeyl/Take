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

# The relay runs on the engineer's machine. The host is resolved at startup
# from the JUCE session file, TAKE_RELAY_HOST, or a prompt — see below.
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


def run_heartbeat(relay_url, code, stop_evt, on_dead):
    engineer_was_alive = None
    missed = 0
    relay = urlparse(relay_url)
    while not stop_evt.is_set():
        # Time a TCP connect to the relay — one network round trip — for the
        # backing-track advance (loop_latency.py).
        try:
            t = time.perf_counter()
            socket.create_connection((relay.hostname, relay.port), timeout=3).close()
            loop_latency.add_rtt(time.perf_counter() - t)
        except OSError:
            pass
        try:
            requests.post(f"{relay_url}/session/{code}/heartbeat",
                          json={"role": "artist"}, timeout=3)
        except requests.RequestException:
            pass
        try:
            r = requests.get(f"{relay_url}/session/{code}/status", timeout=3)
            if r.ok:
                engineer_alive = r.json()["engineer"]
                loop_latency.update_engineer(r.json().get("latency"))
                if engineer_alive:
                    if engineer_was_alive is False:
                        print("✓ Engineer reconnected", flush=True)
                    missed = 0
                else:
                    missed += 1
                    if engineer_was_alive is True:
                        print("⚠ Engineer disconnected", flush=True)
                    if missed >= 5 and not stop_evt.is_set():
                        on_dead()
                        return
                engineer_was_alive = engineer_alive
        except requests.RequestException:
            pass
        stop_evt.wait(5)


def _read_session_file():
    """Wait — however long it takes — for the artist app to join a session
    and write the session file (engineer IP + code). Joining can take a
    while (finding the code, typing the engineer's address by hand), and the
    backend is no use until it happens."""
    waited = 0
    while True:
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE) as f:
                    data = json.load(f)
                written_at_ms = data.get("written_at", 0)
                age_s = (time.time() * 1000 - written_at_ms) / 1000
                if written_at_ms and age_s > 60:
                    print(f"Ignoring stale session file (age {age_s:.0f}s)")
                    os.unlink(SESSION_FILE)
                    time.sleep(1)
                    continue
                os.unlink(SESSION_FILE)
                ip = data.get("engineer_ip", "")
                code = data.get("code", "")
                if ip and code:
                    return ip, code
            except Exception:
                pass
        time.sleep(1)
        waited += 1
        if waited % 60 == 0:
            print(f"Still waiting for the artist app to join a session "
                  f"({waited // 60} min)...", flush=True)


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

    print("Waiting for session code from JUCE app...", flush=True)
    TARGET_IP, code = _read_session_file()

    # The relay lives on the engineer's machine: TAKE_RELAY_HOST if set,
    # otherwise the engineer IP the artist app joined with.
    relay_host = os.environ.get("TAKE_RELAY_HOST") or TARGET_IP
    RELAY_URL = f"http://{relay_host}:{RELAY_PORT}"
    print(f"Relay: {RELAY_URL}")

    local_ip = get_local_ip()

    MAX_WAIT = 60
    start_time = time.time()
    while True:
        try:
            resp = requests.post(f"{RELAY_URL}/session/join",
                                 json={"code": code, "ip": local_ip}, timeout=5)
            resp.raise_for_status()
            break
        except Exception as e:
            elapsed = time.time() - start_time
            if elapsed > MAX_WAIT:
                print(f"Could not connect to relay after {MAX_WAIT}s. Is the engineer running?")
                sys.exit(1)
            print(f"Waiting for engineer... ({int(elapsed)}s)")
            time.sleep(3)

    TARGET_IP = resp.json()["engineer_ip"]
    print(f"Engineer found — {TARGET_IP}")

    # Write relay host so the JUCE app reads it before making its own join call
    with open(SESSION_FILE, "w") as f:
        json.dump({"engineer_ip": TARGET_IP, "code": code,
                   "written_at": int(time.time() * 1000)}, f)

    watcher.TARGET_IP = TARGET_IP
    artist.TARGET_IP = TARGET_IP
    transport.RELAY_URL = RELAY_URL  # Reaper record/stop commands route through the relay

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
        threading.Thread(
            target=run_heartbeat,
            args=(RELAY_URL, code, stop_event,
                  lambda: shutdown("Session ended — engineer disconnected")),
            name="heartbeat",
            daemon=True,
        ),
        threading.Thread(target=timecode.receiver, args=(stop_event,),
                         name="timecode", daemon=True),
    ]
    for t in threads:
        t.start()

    print("Take — artist ready")
    print(f"  Watching        : {WATCH_PATH}")
    print(f"  File transfer   : {TARGET_IP}:{FILE_PORT}")
    print(f"  Mic stream out  : {TARGET_IP}:{STREAM_PORT}")
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

    try:
        requests.delete(f"{RELAY_URL}/session/{code}", timeout=3)
    except requests.RequestException:
        pass

    for t in threads:
        t.join(timeout=2)

    sys.exit(0)
