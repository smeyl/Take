import os
import logging
import threading
import requests

import receiver
from receiver import app, INCOMING_PATH, PORT
from reaper import BASE

ACTION_INSERT_MEDIA = "_RSb5c2380eebd5068bc425e17e9f920644a2f49be8"
TEMP_FILE = "/tmp/take_incoming.txt"


def _insert_media_flow(filename):
    filepath = os.path.join(INCOMING_PATH, filename)
    try:
        with open(TEMP_FILE, "w") as f:
            f.write(filepath)
        requests.get(f"{BASE}/_/{ACTION_INSERT_MEDIA}", timeout=5)
        print(f"Reaper: placed {filename} on timeline")
    except requests.ConnectionError:
        print(f"Reaper: connection failed — could not place {filename}")


def _on_file_received(filename, size):
    threading.Thread(target=_insert_media_flow, args=(filename,), daemon=True).start()


receiver.on_file_received = _on_file_received


def run_receiver():
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    os.makedirs(INCOMING_PATH, exist_ok=True)
    app.run(host="0.0.0.0", port=PORT, use_reloader=False)


if __name__ == "__main__":
    threading.Thread(target=run_receiver, name="receiver", daemon=True).start()

    print("Take — engineer ready")
    print(f"  File receiver : 0.0.0.0:{PORT} → {INCOMING_PATH}/")
    print(f"  Reaper        : {ACTION_INSERT_MEDIA}")

    try:
        while True:
            threading.Event().wait(timeout=1)
    except KeyboardInterrupt:
        print("\nShutting down.")
