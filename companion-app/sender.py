import os
import sys
import requests

PORT = 5001


def send_file(filepath, host):
    url = f"http://{host}:{PORT}/upload"
    filename = os.path.basename(filepath)
    try:
        with open(filepath, "rb") as f:
            response = requests.post(url, files={"file": (filename, f)})
        if response.status_code == 200:
            print(f"Sent: {filename} -> {host}:{PORT}")
            return True
        print(f"Failed: {filename} — server returned {response.status_code}")
        return False
    except Exception as e:
        print(f"Failed: {filename} — {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python sender.py <filepath> [host]")
        sys.exit(1)
    host = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1"
    success = send_file(sys.argv[1], host)
    sys.exit(0 if success else 1)
