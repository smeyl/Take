#!/bin/bash
cd "$(dirname "$0")"

# --- Ensure Python 3 is available -------------------------------------------
# On a brand-new Mac /usr/bin/python3 is a stub that fails until Apple's
# Command Line Tools are installed.
if ! /usr/bin/python3 --version >/dev/null 2>&1; then
    echo "ERROR: Python 3 is not available at /usr/bin/python3."
    echo "Install Apple's Command Line Tools first, then re-run this script:"
    echo ""
    echo "    xcode-select --install"
    echo ""
    exit 1
fi

# --- Ensure portaudio is installed (required to build pyaudio) ---------------
have_portaudio() {
    # Homebrew installs libportaudio under /opt/homebrew (Apple Silicon) or
    # /usr/local (Intel). Either presence means pyaudio can build. Check each
    # path independently: a single `ls a b` fails if *either* arg is missing,
    # and one of these prefixes never exists on a given Mac.
    for dir in /opt/homebrew/lib /usr/local/lib; do
        for f in "$dir"/libportaudio*.dylib; do
            [ -e "$f" ] && return 0
        done
    done
    return 1
}

if ! have_portaudio; then
    echo "portaudio not found — it's required to build the 'pyaudio' package."
    if ! command -v brew >/dev/null 2>&1; then
        echo ""
        echo "ERROR: Homebrew is not installed, so portaudio can't be set up"
        echo "automatically. Install Homebrew first:"
        echo ""
        echo '    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
        echo ""
        echo "Then re-run ./setup.sh."
        exit 1
    fi
    echo "Installing portaudio via Homebrew..."
    if ! brew install portaudio; then
        echo ""
        echo "ERROR: 'brew install portaudio' failed. Fix the error above and"
        echo "re-run ./setup.sh."
        exit 1
    fi
fi

# --- Install Python packages ------------------------------------------------
echo "Installing Take Python dependencies..."
PACKAGES=(flask flask-cors requests pyaudio watchdog soundfile sounddevice numpy pedalboard)
for pkg in "${PACKAGES[@]}"; do
    echo "  → $pkg"
    if ! /usr/bin/python3 -m pip install "$pkg"; then
        echo ""
        echo "ERROR: failed to install '$pkg'. Setup aborted — nothing else will run."
        echo "Fix the error shown above and re-run ./setup.sh."
        exit 1
    fi
done

echo "Installing Reaper scripts..."
SCRIPTS="$HOME/Library/Application Support/REAPER/Scripts"
mkdir -p "$SCRIPTS"
cp take_session.lua "$SCRIPTS/"

# Auto-start the session script with Reaper (idempotent)
STARTUP="$SCRIPTS/__startup.lua"
DOFILE='dofile(reaper.GetResourcePath() .. "/Scripts/take_session.lua")'
if [ ! -f "$STARTUP" ] || ! grep -qF "take_session.lua" "$STARTUP"; then
    echo "$DOFILE" >> "$STARTUP"
fi

# Remove scripts superseded by take_session.lua
rm -f "$SCRIPTS/take_reaper_poll.lua" \
      "$SCRIPTS/take_export_tracks.lua" \
      "$SCRIPTS/take_export_markers.lua" \
      "$SCRIPTS/take_insert_media.lua"

echo "Setup complete — zero Reaper configuration needed."
echo "On every Reaper launch the Take script starts automatically, keeps track"
echo "and marker exports current, and self-registers the insert action."
