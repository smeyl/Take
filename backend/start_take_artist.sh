#!/bin/bash
cd "$(dirname "$0")"
rm -f /tmp/take_session.json
# Resolve the JUCE app relative to this script — the repo may live anywhere
open "$(pwd)/../artist-app/Take/Builds/MacOSX/build/Debug/Take.app"
/usr/bin/python3 start_artist.py
