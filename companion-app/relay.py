import random
import string
import time
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

SESSION_TTL = 24 * 3600
sessions = {}  # code -> {engineer_ip, artist_ip, created_at}

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
    data = request.get_json(force=True) or {}
    engineer_ip = data.get("ip") or request.remote_addr
    code = generate_code()
    sessions[code] = {"engineer_ip": engineer_ip, "artist_ip": None, "created_at": time.time()}
    log(f"New session {code} — engineer {engineer_ip}")
    return jsonify({"code": code})


@app.route("/session/join", methods=["POST"])
def join_session():
    prune_expired()
    data = request.get_json(force=True) or {}
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


@app.route("/session/<code>", methods=["DELETE"])
def end_session(code):
    if code not in sessions:
        return jsonify({"error": "session not found"}), 404
    del sessions[code]
    log(f"Session {code} ended")
    return jsonify({"status": "ended"})


if __name__ == "__main__":
    log("Take relay server starting on port 5000")
    app.run(host="0.0.0.0", port=5010)
