#!/bin/bash
cd "$(dirname "$0")"

cleanup() {
    kill "$RELAY_PID" 2>/dev/null
}
trap cleanup EXIT

python3 relay.py &
RELAY_PID=$!
sleep 1
python3 start_engineer.py
