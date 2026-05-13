#!/bin/bash
cd "$(dirname "$0")"
python3 relay.py &
RELAY_PID=$!
sleep 1
python3 start_engineer.py
kill $RELAY_PID
