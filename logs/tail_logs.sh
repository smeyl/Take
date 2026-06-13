#!/bin/bash
# Tail every Take log at once. Ctrl-C to stop.
cd "$(dirname "$0")"

# Make sure the files exist so tail doesn't bail on a fresh checkout.
touch artist.log engineer.log electron.log

# -F follows by name, so it keeps working if a log is recreated on relaunch.
tail -n 50 -F artist.log engineer.log electron.log
