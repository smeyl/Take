#!/bin/bash
echo "Installing Take dependencies..."
/usr/bin/python3 -m pip install flask flask-cors requests pyaudio \
  watchdog soundfile sounddevice numpy pedalboard
echo "Setup complete."
