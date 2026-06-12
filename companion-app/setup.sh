#!/bin/bash
cd "$(dirname "$0")"

echo "Installing Take dependencies..."
/usr/bin/python3 -m pip install flask flask-cors requests pyaudio \
  watchdog soundfile sounddevice numpy pedalboard

echo "Installing Reaper scripts..."
SCRIPTS="$HOME/Library/Application Support/REAPER/Scripts"
mkdir -p "$SCRIPTS"
cp take_session.lua take_insert_media.lua "$SCRIPTS/"

# Auto-start the session script with Reaper (idempotent)
STARTUP="$SCRIPTS/__startup.lua"
DOFILE='dofile(reaper.GetResourcePath() .. "/Scripts/take_session.lua")'
if [ ! -f "$STARTUP" ] || ! grep -qF "take_session.lua" "$STARTUP"; then
    echo "$DOFILE" >> "$STARTUP"
fi

# Remove scripts superseded by take_session.lua
rm -f "$SCRIPTS/take_reaper_poll.lua" \
      "$SCRIPTS/take_export_tracks.lua" \
      "$SCRIPTS/take_export_markers.lua"

echo "Setup complete."
echo "Reaper will create and arm a 'Take Session' track automatically on launch."
echo "One manual step remains: register take_insert_media.lua as an action"
echo "(Actions → Show action list → New action → Load ReaScript) and put its"
echo "command ID in companion-app/engineer.py (ACTION_INSERT_MEDIA)."
