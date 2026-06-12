#!/bin/bash
cd "$(dirname "$0")"

# Kill any leftover processes on our ports (incl. zombie relay/bounce from a crashed run)
lsof -ti :5001 | xargs kill -9 2>/dev/null
lsof -ti :5002 | xargs kill -9 2>/dev/null
lsof -ti :5006 | xargs kill -9 2>/dev/null
lsof -ti :5010 | xargs kill -9 2>/dev/null
sleep 0.5

cleanup() {
    kill "$RELAY_PID" 2>/dev/null
}
trap cleanup EXIT

/usr/bin/python3 relay.py &
RELAY_PID=$!
sleep 1
export PYTHONWARNINGS="ignore"
/usr/bin/python3 start_engineer.py 2>>/tmp/take_engineer_error.log

if [ -s /tmp/take_engineer_error.log ]; then
    echo "=== Engineer errors ==="
    cat /tmp/take_engineer_error.log
fi
