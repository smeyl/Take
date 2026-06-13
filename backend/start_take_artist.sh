#!/bin/bash
cd "$(dirname "$0")"
rm -f /tmp/take_session.json
open ~/Desktop/Take/artist-app/Take/Builds/MacOSX/build/Debug/Take.app
/usr/bin/python3 start_artist.py
