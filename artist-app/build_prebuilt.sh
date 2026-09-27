#!/bin/bash
# Rebuild the committed artist app, artist-app/prebuilt/Take.app, from the
# JUCE project: Release, universal (Apple Silicon + Intel). A fresh clone runs
# this app — nobody but developers has Xcode and JUCE — so after changing the
# artist app's code, run this and commit artist-app/prebuilt.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
xcodebuild -project "$HERE/Take/Builds/MacOSX/Take.xcodeproj" -configuration Release -quiet
rm -rf "$HERE/prebuilt/Take.app"
mkdir -p "$HERE/prebuilt"
ditto "$HERE/Take/Builds/MacOSX/build/Release/Take.app" "$HERE/prebuilt/Take.app"
echo "prebuilt/Take.app updated ($(lipo -archs "$HERE/prebuilt/Take.app/Contents/MacOS/Take"), $(du -sh "$HERE/prebuilt/Take.app" | cut -f1)) — commit artist-app/prebuilt"
