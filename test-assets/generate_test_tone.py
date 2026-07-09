#!/usr/bin/env python3
"""Generate a test backing track for end-to-end pipeline checks.

Produces a 20-second click track: a short 1 kHz tone burst every second
(20 clear, evenly spaced peaks), mono, 44.1 kHz, 16-bit WAV. The regular
clicks make it easy to eyeball the artist app's waveform, ruler (0:00–0:20),
and playhead sync, and to place markers at known positions.

Usage:
    python3 test-assets/generate_test_tone.py [output.wav]

Defaults to ./take_test_tone.wav. To exercise the artist's backing-track
player directly (no Reaper needed), write it to the path the player watches:

    python3 test-assets/generate_test_tone.py incoming/take_backing_track.mp3

(libsndfile reads by file content, so the .mp3 name is fine for a WAV.)
The committed generator — rather than the 1.7 MB WAV — keeps it out of git
history; regenerate on demand.
"""
import sys

import numpy as np
import soundfile as sf

RATE = 44100
DURATION = 20.0     # seconds
CLICK_MS = 60       # length of each tone burst
CLICK_HZ = 1000.0   # click pitch


def main(out_path):
    n = int(RATE * DURATION)
    audio = np.zeros(n, dtype=np.float32)

    click_len = int(RATE * CLICK_MS / 1000)
    t = np.arange(click_len) / RATE
    env = np.hanning(click_len).astype(np.float32)  # fade in/out so it doesn't pop
    click = (0.6 * np.sin(2 * np.pi * CLICK_HZ * t) * env).astype(np.float32)

    for sec in range(int(DURATION)):
        start = sec * RATE
        audio[start:start + click_len] = click

    sf.write(out_path, audio, RATE, subtype="PCM_16")
    info = sf.info(out_path)
    print(f"wrote {out_path}: {info.duration:.1f}s, {info.samplerate}Hz, "
          f"{info.channels}ch, {info.subtype}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "take_test_tone.wav")
