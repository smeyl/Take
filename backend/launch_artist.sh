#!/bin/bash
# What Take Artist.app runs in its Terminal window: set Take up if this is a
# fresh copy (stop here if that fails), start the artist backend in the
# background, then open the artist app. Output shows in the window and is
# appended to logs/artist.log.
BACKEND="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$BACKEND/.." && pwd)"
LOGS="$ROOT/logs"
mkdir -p "$LOGS"
export PYTHONUNBUFFERED=1

/bin/bash "$BACKEND/first_run.sh" artist || exit 1
APP="$(/bin/bash "$BACKEND/artist_app_path.sh")"

(/bin/bash "$BACKEND/dev_artist.sh" 2>&1 | tee -a "$LOGS/artist.log") &
sleep 3
echo "Opening $APP" | tee -a "$LOGS/artist.log"
open "$APP" 2>&1 | tee -a "$LOGS/artist.log"
wait
