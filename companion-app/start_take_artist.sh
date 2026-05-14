#!/bin/bash
cd "$(dirname "$0")"
/usr/bin/python3 start_artist.py &
ARTIST_PID=$!
open ~/Desktop/Take/app/Take/Builds/MacOSX/build/Debug/Take.app
wait $ARTIST_PID
