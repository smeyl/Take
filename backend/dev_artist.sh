#!/bin/bash
cd "$(dirname "$0")"

rm -f /tmp/take_session.json

# Replace any artist backend already running — including one still waiting
# for a join, which holds no ports yet — so a stale one never serves alongside.
pkill -f "start_artist.py" 2>/dev/null
# Kill any leftover processes on our ports
lsof -ti :5003 | xargs kill -9 2>/dev/null
lsof -ti :5004 | xargs kill -9 2>/dev/null
lsof -ti :5005 | xargs kill -9 2>/dev/null
lsof -ti :5007 | xargs kill -9 2>/dev/null
lsof -ti :5009 | xargs kill -9 2>/dev/null
sleep 0.5
export PYTHONWARNINGS="ignore"
/usr/bin/python3 start_artist.py
