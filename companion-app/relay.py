import hashlib
import random
import socket as _socket
import string
import time
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests as _requests
import reaper

app = Flask(__name__)
CORS(app)

import logging
logging.getLogger('werkzeug').setLevel(logging.ERROR)

SESSION_TTL = 24 * 3600
HEARTBEAT_TTL = 15  # seconds before a role is considered dead
sessions = {}  # code -> {engineer_ip, artist_ip, created_at, heartbeats}

timecode_state = {"pos": 0.0, "playing": False}
punch_state    = {"in": 0.0, "out": 0.0, "active": False}
auto_sync      = True
selected_track = 0  # destination track index, set from the engineer UI

CHARS = string.ascii_uppercase + string.digits
CUE_PORT = 5003


def generate_code():
    return "".join(random.choices(CHARS, k=6))


def _hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def get_local_ip():
    """LAN IP of this machine — the relay always runs on the engineer's machine."""
    with _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM) as s:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]


def _resolve_ip(ip, fallback):
    """Loopback addresses are useless to the peer on another machine."""
    if not ip or ip.startswith("127.") or ip == "localhost":
        return fallback
    return ip


def prune_expired():
    now = time.time()
    expired = [c for c, s in sessions.items() if now - s["created_at"] > SESSION_TTL]
    for c in expired:
        del sessions[c]


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


@app.route("/session/new", methods=["POST"])
def new_session():
    prune_expired()
    data = request.get_json(force=True, silent=True) or {}
    # The relay runs on the engineer's machine, so its own LAN IP is the
    # correct fallback when the caller is local or sends a loopback address.
    engineer_ip = _resolve_ip(data.get("ip") or request.remote_addr, get_local_ip())
    password = (data.get("password") or "").strip()
    code = generate_code()
    sessions[code] = {
        "engineer_ip": engineer_ip,
        "artist_ip": None,
        "created_at": time.time(),
        "heartbeats": {"engineer": None, "artist": None},
        "password_hash": _hash_password(password) if password else None,
    }
    log(f"New session {code} — engineer {engineer_ip}"
        + (" (password protected)" if password else ""))
    return jsonify({"code": code})


ACTIVE_TTL = 5 * 60  # 5 minutes


@app.route("/session/active", methods=["GET"])
def active_session():
    now = time.time()
    recent = [(code, s) for code, s in sessions.items()
              if now - s["created_at"] < ACTIVE_TTL]
    if not recent:
        return jsonify({"error": "no active session"}), 404
    code, s = max(recent, key=lambda x: x[1]["created_at"])
    return jsonify({"code": code, "engineer_ip": s["engineer_ip"]})


@app.route("/session/join", methods=["POST"])
def join_session():
    prune_expired()
    data = request.get_json(force=True, silent=True) or {}
    code = data.get("code", "")
    artist_ip = _resolve_ip(data.get("ip"), request.remote_addr)
    if code not in sessions:
        return jsonify({"error": "session not found"}), 404
    pw_hash = sessions[code].get("password_hash")
    if pw_hash and _hash_password((data.get("password") or "").strip()) != pw_hash:
        log(f"Join rejected for session {code} — wrong password ({artist_ip})")
        return jsonify({"error": "wrong password"}), 403
    sessions[code]["artist_ip"] = artist_ip
    engineer_ip = sessions[code]["engineer_ip"]
    log(f"Artist {artist_ip} joined session {code} — engineer is {engineer_ip}")
    return jsonify({"engineer_ip": engineer_ip})


@app.route("/session/<code>", methods=["GET"])
def get_session(code):
    prune_expired()
    if code not in sessions:
        return jsonify({"error": "session not found"}), 404
    s = sessions[code]
    if s["artist_ip"] is None:
        return jsonify({"status": "waiting"}), 202
    return jsonify({"engineer_ip": s["engineer_ip"], "artist_ip": s["artist_ip"]})


@app.route("/session/<code>/heartbeat", methods=["POST"])
def heartbeat(code):
    if code not in sessions:
        return jsonify({"error": "session not found"}), 404
    data = request.get_json(force=True, silent=True) or {}
    role = data.get("role")
    if role not in ("engineer", "artist"):
        return jsonify({"error": "invalid role"}), 400
    sessions[code]["heartbeats"][role] = time.time()
    return jsonify({"ok": True})


@app.route("/session/<code>/status", methods=["GET"])
def session_status(code):
    if code not in sessions:
        return jsonify({"error": "session not found"}), 404
    now = time.time()
    hb = sessions[code]["heartbeats"]
    engineer_alive = hb["engineer"] is not None and now - hb["engineer"] < HEARTBEAT_TTL
    artist_alive = hb["artist"] is not None and now - hb["artist"] < HEARTBEAT_TTL
    return jsonify({
        "engineer": engineer_alive,
        "artist": artist_alive,
        "both_alive": engineer_alive and artist_alive,
    })


@app.route("/session/<code>", methods=["DELETE"])
def end_session(code):
    if code not in sessions:
        return jsonify({"error": "session not found"}), 404
    del sessions[code]
    log(f"Session {code} ended")
    return jsonify({"status": "ended"})


# Maps UI knob keys → cue_receiver.py param names.
_CUE_PARAM_MAP = {
    "rev":    "reverb",       # room size  → Reverb.room_size
    "revMix": "reverbMix",    # wet/dry    → Reverb.wet_level / dry_level
    "del":    "delay",        # time       → Delay.delay_seconds
    "delMix": "delayMix",     # wet/dry    → Delay.mix
    "comp":   "compression",  # threshold  → stored, DSP pass-through for now
    "vol":    "volume",       # output gain
    # "ratio" absent — no backing state in UI or DSP
}


def _latest_artist_ip():
    """Artist IP of the most recently created session with both peers joined."""
    joined = [s for s in sessions.values()
              if s.get("engineer_ip") and s.get("artist_ip")]
    if not joined:
        return None
    return max(joined, key=lambda s: s["created_at"])["artist_ip"]


@app.route("/cue/<param>/<value>", methods=["POST"])
def cue_forward(param, value):
    dsp_name = _CUE_PARAM_MAP.get(param)
    if dsp_name is None:
        return jsonify({"ok": True, "dropped": True})  # no DSP equivalent
    artist_ip = _latest_artist_ip()
    if not artist_ip:
        return jsonify({"error": "artist not connected"}), 404
    msg = f"{dsp_name}:{value}".encode()
    sock = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
    try:
        sock.sendto(msg, (artist_ip, CUE_PORT))
    finally:
        sock.close()
    return jsonify({"ok": True})


# ── Artist-machine proxy ──────────────────────────────────────────────────────
# The engineer UI can only reach localhost; the transport (5004) and stream
# quality (5007) servers run on the artist's machine. These routes forward to
# the artist IP of the current session so the UI works across two machines.

_ARTIST_ROUTES = {
    "record":         (5004, "/record"),
    "stop":           (5004, "/stop"),
    "status":         (5004, "/status"),
    "levels":         (5004, "/levels"),
    "stream-quality": (5007, "/stream-quality"),
}

_SYNC_FORMAT_FILE = "/tmp/take_sync_format"


def _read_tmp(path, default):
    try:
        with open(path) as fh:
            return fh.read().strip()
    except OSError:
        return default


@app.route("/artist/<endpoint>", methods=["GET", "POST"])
def artist_proxy(endpoint):
    route = _ARTIST_ROUTES.get(endpoint)
    if route is None:
        return jsonify({"error": "unknown endpoint"}), 404
    artist_ip = _latest_artist_ip()
    if not artist_ip:
        return jsonify({"error": "artist not connected"}), 404
    port, path = route
    url = f"http://{artist_ip}:{port}{path}"
    payload = request.get_json(force=True, silent=True) or {}
    if endpoint == "record":
        # Sync format lives on this (engineer) machine; the artist's transport
        # can't read it across the network. The destination track is no longer
        # sent — take_session.lua always records onto the Take Session track.
        payload.setdefault("format", _read_tmp(_SYNC_FORMAT_FILE, "WAV24"))
    try:
        if request.method == "POST":
            r = _requests.post(url, json=payload, timeout=5)
        else:
            r = _requests.get(url, timeout=2)
        return r.text, r.status_code, {"Content-Type": r.headers.get("Content-Type", "application/json")}
    except _requests.RequestException as e:
        return jsonify({"error": f"artist unreachable: {e}"}), 502


# ── Reaper transport ──────────────────────────────────────────────────────────
# Reaper always runs on the engineer's machine (next to the relay). The artist's
# transport calls these when recording starts/stops so the live BlackHole
# recording in Reaper follows the artist's lossless local recording.

@app.route("/track/select/<int:index>", methods=["POST"])
def select_track(index):
    """Remember the destination track. Reaper isn't touched until record time —
    the record command arms this track as it starts rolling."""
    global selected_track
    selected_track = index
    try:
        # engineer.py reads this for the fallback insert path
        with open("/tmp/take_dest_track", "w") as fh:
            fh.write(str(index))
    except OSError:
        pass
    log(f"Destination track → {index}")
    return jsonify({"ok": True, "selected_track": index})


@app.route("/reaper/record", methods=["POST"])
def reaper_record():
    # take_session.lua arms the selected track and starts the transport
    reaper.start_recording(selected_track)
    return jsonify({"ok": True, "track": selected_track})


@app.route("/reaper/stop", methods=["POST"])
def reaper_stop():
    reaper.stop_recording()
    return jsonify({"ok": True})


@app.route("/reaper/rtz", methods=["POST"])
def reaper_rtz():
    reaper.return_to_zero()
    return jsonify({"ok": True})


@app.route("/timecode", methods=["GET"])
def get_timecode():
    return jsonify(timecode_state)


@app.route("/timecode", methods=["POST"])
def post_timecode():
    data = request.get_json(force=True, silent=True) or {}
    timecode_state["pos"]     = float(data.get("pos", 0.0))
    timecode_state["playing"] = bool(data.get("playing", False))
    return jsonify({"ok": True})


@app.route("/punch", methods=["GET"])
def get_punch():
    return jsonify(punch_state)


@app.route("/punch", methods=["POST"])
def set_punch():
    data     = request.get_json(force=True, silent=True) or {}
    punch_in  = float(data.get("in",  0.0))
    punch_out = float(data.get("out", 0.0))
    # explicit active=false clears the zone; otherwise infer from values
    if "active" in data and not data["active"]:
        punch_state["in"]     = 0.0
        punch_state["out"]    = 0.0
        punch_state["active"] = False
    else:
        punch_state["in"]     = punch_in
        punch_state["out"]    = punch_out
        punch_state["active"] = punch_in > 0.0 or punch_out > 0.0
    return jsonify({"ok": True})


@app.route("/takes/<path:filename>/swap", methods=["POST"])
def manual_take_swap(filename):
    """Forward a manual swap request to the file receiver on this machine."""
    try:
        r = _requests.post(f"http://127.0.0.1:5001/takes/{filename}/swap", timeout=5)
        return r.text, r.status_code, {"Content-Type": r.headers.get("Content-Type", "application/json")}
    except _requests.RequestException as e:
        return jsonify({"error": f"file receiver unreachable: {e}"}), 502


@app.route("/auto-sync", methods=["GET"])
def get_auto_sync():
    return jsonify({"enabled": auto_sync})


@app.route("/auto-sync", methods=["POST"])
def set_auto_sync():
    global auto_sync
    data = request.get_json(force=True, silent=True) or {}
    auto_sync = bool(data.get("enabled", True))
    log(f"Auto-sync {'enabled' if auto_sync else 'disabled'}")
    return jsonify({"enabled": auto_sync})


@app.route("/tracks", methods=["GET"])
def get_tracks():
    """Track list for the engineer UI — proxied to the file receiver."""
    try:
        r = _requests.get("http://127.0.0.1:5001/tracks", timeout=2)
        return r.text, r.status_code, {"Content-Type": r.headers.get("Content-Type", "application/json")}
    except _requests.RequestException:
        return jsonify([])


@app.route("/markers", methods=["GET"])
def get_markers():
    return jsonify(reaper.get_markers())


@app.route("/reaper/status", methods=["GET"])
def reaper_status():
    try:
        _requests.get("http://localhost:8080", timeout=2)
        return jsonify({"reachable": True})
    except _requests.RequestException:
        return jsonify({"reachable": False})


if __name__ == "__main__":
    import ports
    ports.ensure_free([(5010, "tcp", "relay")])
    log("Take relay server starting on port 5010")
    app.run(host="0.0.0.0", port=5010)
