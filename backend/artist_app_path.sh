#!/bin/bash
# Prints the artist app Take Artist.app should open: the newer of the committed
# build (artist-app/prebuilt) and a local Xcode build. A developer's fresh
# build wins, but a stale local build can't shadow a newer committed app.
# Prints nothing if there's no app at all.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
best=""; best_t=0
for app in "$ROOT/artist-app/prebuilt/Take.app" \
           "$ROOT/artist-app/Take/Builds/MacOSX/build/Debug/Take.app" \
           "$ROOT/artist-app/Take/Builds/MacOSX/build/Release/Take.app"; do
    exe="$app/Contents/MacOS/Take"
    [ -f "$exe" ] || continue
    t=$(stat -f %m "$exe")
    if [ "$t" -gt "$best_t" ]; then best="$app"; best_t=$t; fi
done
echo "$best"
