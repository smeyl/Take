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

echo "Setup complete — zero Reaper configuration needed."
echo "On every Reaper launch the Take script starts automatically, keeps track"
echo "and marker exports current, and self-registers the insert action."
