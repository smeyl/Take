#!/usr/bin/env python3
"""Generate the Take app icons and install them into the app bundles.

Run:  python3 assets/make_icons.py      (from anywhere; paths are resolved
                                          relative to this file)

Requires Pillow:  /usr/bin/python3 -m pip install --user Pillow

Generated PNG/icns/iconset files are written next to this script in assets/
and are git-ignored; only this script is tracked. The finished icons are
copied into both app bundles as Contents/Resources/AppIcon.icns (the
Info.plist of each bundle already sets CFBundleIconFile = AppIcon).

────────────────────────────────────────────────────────────────────────────
ICON SPEC
────────────────────────────────────────────────────────────────────────────
Shared:
  - 1024x1024, background #0a0a0b, rounded square with corner radius 180
  - Rendered at 4x and downsampled (LANCZOS) for clean antialiased strokes
  - Iconset sizes: 16, 32, 128, 256, 512 (each with @2x), via iconutil

ENGINEER  — two overlapping circles (stroke only)
  - Left  circle: center (460, 512), radius 280, stroke #2dd4bf, width 26
  - Right circle: center (564, 512), radius 280, stroke #4f8fff, width 26

ARTIST    — single filled circle with subtle fill
  - Circle: center (512, 512), radius 300
  - Fill:   #2dd4bf at opacity 0.15 (alpha-composited over the background)
  - Stroke: #2dd4bf, width 26
────────────────────────────────────────────────────────────────────────────
"""
import os
import subprocess

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))      # …/Take/assets
REPO = os.path.dirname(HERE)                           # …/Take

SIZE = 1024
SCALE = 4  # supersample factor
BG = (0x0A, 0x0A, 0x0B, 255)     # #0a0a0b
TEAL = (0x2D, 0xD4, 0xBF, 255)   # #2dd4bf
BLUE = (0x4F, 0x8F, 0xFF, 255)   # #4f8fff
CORNER_RADIUS = 180

# name -> path of the .app bundle that should receive the icon
BUNDLES = {
    "engineer": os.path.join(REPO, "Take Engineer.app"),
    "artist": os.path.join(REPO, "Take Artist.app"),
}


def _new_base():
    """Rounded-square dark background at supersampled resolution."""
    px = SIZE * SCALE
    img = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle(
        [(0, 0), (px - 1, px - 1)], radius=CORNER_RADIUS * SCALE, fill=BG,
    )
    return img


def _ellipse_box(cx, cy, r):
    s = SCALE
    return [((cx - r) * s, (cy - r) * s), ((cx + r) * s, (cy + r) * s)]


def render_engineer():
    """Two overlapping stroke-only circles."""
    img = _new_base()
    d = ImageDraw.Draw(img)
    d.ellipse(_ellipse_box(460, 512, 280), outline=TEAL, width=26 * SCALE)
    d.ellipse(_ellipse_box(564, 512, 280), outline=BLUE, width=26 * SCALE)
    return img.resize((SIZE, SIZE), Image.LANCZOS)


def render_artist():
    """Single circle: 15%-opacity teal fill + teal stroke."""
    base = _new_base()

    # Translucent fill on its own layer, then alpha-composited so it blends
    # over the dark background instead of punching a hole in it.
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    fill = (TEAL[0], TEAL[1], TEAL[2], round(0.15 * 255))
    ImageDraw.Draw(overlay).ellipse(_ellipse_box(512, 512, 300), fill=fill)
    base = Image.alpha_composite(base, overlay)

    # Opaque stroke on top.
    ImageDraw.Draw(base).ellipse(
        _ellipse_box(512, 512, 300), outline=TEAL, width=26 * SCALE,
    )
    return base.resize((SIZE, SIZE), Image.LANCZOS)


def build_icns(master, name):
    """Write master PNG, build the .iconset, and run iconutil -> .icns."""
    png = os.path.join(HERE, f"{name}_1024.png")
    iconset = os.path.join(HERE, f"{name}.iconset")
    icns = os.path.join(HERE, f"{name}.icns")

    master.save(png)
    os.makedirs(iconset, exist_ok=True)
    for base in (16, 32, 128, 256, 512):
        for retina in (False, True):
            px = base * 2 if retina else base
            fn = f"icon_{base}x{base}{'@2x' if retina else ''}.png"
            master.resize((px, px), Image.LANCZOS).save(os.path.join(iconset, fn))

    subprocess.run(["iconutil", "-c", "icns", iconset, "-o", icns], check=True)
    return icns


def install(icns, bundle):
    """Copy the .icns into the bundle as Contents/Resources/AppIcon.icns."""
    resources = os.path.join(bundle, "Contents", "Resources")
    os.makedirs(resources, exist_ok=True)
    dest = os.path.join(resources, "AppIcon.icns")
    with open(icns, "rb") as src, open(dest, "wb") as out:
        out.write(src.read())
    os.utime(bundle, None)  # bump mtime so Finder/Dock repaints
    print(f"installed {os.path.basename(icns)} -> {dest}")


RENDERERS = {"engineer": render_engineer, "artist": render_artist}

if __name__ == "__main__":
    for name, render in RENDERERS.items():
        icns = build_icns(render(), name)
        install(icns, BUNDLES[name])
    # Repaint Dock/Finder so the new icons show immediately (non-fatal).
    subprocess.run(["killall", "Dock", "Finder"], check=False)
    print("done.")
