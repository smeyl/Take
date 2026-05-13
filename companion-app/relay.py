import random
import string
import time
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests as _requests

app = Flask(__name__)
CORS(app)

SESSION_TTL = 24 * 3600
HEARTBEAT_TTL = 15  # seconds before a role is considered dead
sessions = {}  # code -> {engineer_ip, artist_ip, created_at, heartbeats}

CHARS = string.ascii_uppercase + string.digits


def generate_code():
    return "".join(random.choices(CHARS, k=6))


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
    engineer_ip = data.get("ip") or request.remote_addr
    code = generate_code()
    sessions[code] = {
        "engineer_ip": engineer_ip,
        "artist_ip": None,
        "created_at": time.time(),
        "heartbeats": {"engineer": None, "artist": None},
    }
    log(f"New session {code} — engineer {engineer_ip}")
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
    artist_ip = data.get("ip") or request.remote_addr
    if code not in sessions:
        return jsonify({"error": "session not found"}), 404
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


@app.route("/reaper/status", methods=["GET"])
def reaper_status():
    try:
        _requests.get("http://localhost:8080", timeout=2)
        return jsonify({"reachable": True})
    except _requests.RequestException:
        return jsonify({"reachable": False})


if __name__ == "__main__":
    log("Take relay server starting on port 5000")
    app.run(host="0.0.0.0", port=5010)
