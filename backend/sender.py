import os
import sys
import requests

PORT = 5001  # engineer's take receiver (default); artist's receiver is 5009


def send_file(filepath, host, port=PORT, filename=None):
    # filename overrides the name the receiver saves under (the local file on
    # disk keeps its own name) — used by bounce.py, whose renders are uniquely
    # named locally but must land at the artist's fixed backing-track path.
    url = f"http://{host}:{port}/upload"
    filename = filename or os.path.basename(filepath)
    try:
        with open(filepath, "rb") as f:
            response = requests.post(url, files={"file": (filename, f)})
        if response.status_code == 200:
            print(f"Sent: {filename} -> {host}:{port}")
            return True
        print(f"Failed: {filename} — server returned {response.status_code}")
        return False
    except Exception as e:
        print(f"Failed: {filename} — {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python sender.py <filepath> [host] [port]")
        sys.exit(1)
    host = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1"
    port = int(sys.argv[3]) if len(sys.argv) > 3 else PORT
    success = send_file(sys.argv[1], host, port)
    sys.exit(0 if success else 1)
