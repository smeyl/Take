#!/bin/bash
# Run by Take Artist.app / Take Engineer.app before anything starts: sets
# Take up on a fresh clone, and does nothing once it is. Checks what's
# actually there (not a marker file) so it also repairs a half-finished setup.
#
#   first_run.sh artist | engineer
#
# Exits non-zero if Take can't run yet; the launcher then stops.
ROLE="$1"
BACKEND="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$BACKEND/.." && pwd)"

MODULES="flask, flask_cors, requests, pyaudio, watchdog, soundfile, sounddevice, numpy, pedalboard"
[ "$ROLE" = "engineer" ] && MODULES="$MODULES, ptsl"

python_ready() {
    /usr/bin/python3 -c "import $MODULES" >/dev/null 2>&1
}

if ! python_ready; then
    echo "First run — setting Take up (one time; this can take a few minutes)..."
    echo ""
    if ! /bin/bash "$BACKEND/setup.sh"; then
        echo ""
        echo "Take isn't set up yet — fix the error above, then open Take again."
        exit 1
    fi
    if ! python_ready; then
        echo ""
        echo "Setup finished, but Python still can't load Take's packages."
        echo "Run  cd \"$BACKEND\" && ./setup.sh  and check its output."
        exit 1
    fi
    echo ""
fi

if [ "$ROLE" = "engineer" ] && [ ! -d "$ROOT/engineer-app/node_modules" ]; then
    if ! command -v npm >/dev/null 2>&1; then
        echo "The engineer app needs Node.js (18 or newer), which isn't installed."
        echo "Install it from https://nodejs.org (or: brew install node), then open Take Engineer again."
        exit 1
    fi
    echo "First run — installing the engineer app's packages (one time)..."
    if ! (cd "$ROOT/engineer-app" && npm install); then
        echo ""
        echo "npm install failed — fix the error above, then open Take Engineer again."
        exit 1
    fi
    echo ""
fi

if [ "$ROLE" = "artist" ] && [ -z "$(/bin/bash "$BACKEND/artist_app_path.sh")" ]; then
    echo "The artist app is missing from this copy of Take — artist-app/prebuilt/Take.app"
    echo "should come with it. Update your copy (git pull), or build it: artist-app/build_prebuilt.sh"
    exit 1
fi

exit 0
