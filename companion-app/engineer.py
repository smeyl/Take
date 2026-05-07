import os
import logging
import threading
import time

import receiver
from receiver import app, INCOMING_PATH, PORT
from reaper import (
    create_track,
    arm_track,
    unarm_track,
    start_recording,
    stop_recording,
)


def _reaper_recording_flow():
    print("Reaper: recording triggered")
    create_track()
    arm_track()
    start_recording()
    time.sleep(0.5)
    stop_recording()
    unarm_track()


def _on_file_received(filename, size):
    threading.Thread(target=_reaper_recording_flow, daemon=True).start()


receiver.on_file_received = _on_file_received


def run_receiver():
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    os.makedirs(INCOMING_PATH, exist_ok=True)
    app.run(host="0.0.0.0", port=PORT, use_reloader=False)


if __name__ == "__main__":
    threading.Thread(target=run_receiver, name="receiver", daemon=True).start()

    print("Take — engineer ready")
    print(f"  File receiver : 0.0.0.0:{PORT} → {INCOMING_PATH}/")
    print(f"  Reaper        : create_track, arm_track, unarm_track, start_recording, stop_recording")

    try:
        while True:
            threading.Event().wait(timeout=1)
    except KeyboardInterrupt:
        print("\nShutting down.")
