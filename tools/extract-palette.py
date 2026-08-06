"""Find the accent colours, not just the most common ones.

The logo is 75% black, so a plain frequency count buries the gold that
actually defines it. Filter for saturated pixels in the hue ranges I care
about and take the dominant shade of each.
"""
import collections
import colorsys
import pathlib

from PIL import Image

SRC = pathlib.Path("assets/source")


def accents(path, hue_lo, hue_hi, min_sat=0.35, min_val=0.35, n=5):
    im = Image.open(path).convert("RGB")
    im.thumbnail((300, 300))
    fam = {}
    for r, g, b in im.getdata():
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        deg = h * 360
        inrange = (hue_lo <= deg <= hue_hi) if hue_lo <= hue_hi else \
            (deg >= hue_lo or deg <= hue_hi)
        if inrange and s >= min_sat and v >= min_val:
            key = (r // 20, g // 20, b // 20)
            e = fam.setdefault(key, [0, 0, 0, 0])
            e[0] += r
            e[1] += g
            e[2] += b
            e[3] += 1
    out = sorted(fam.values(), key=lambda e: -e[3])[:n]
    return ["#{:02X}{:02X}{:02X}".format(e[0] // e[3], e[1] // e[3], e[2] // e[3])
            + f" ({e[3]}px)" for e in out]


print("LOGO gold (hue 35-60):")
for c in accents(SRC / "logo.jpg", 35, 60):
    print("   ", c)
print("\nLOGO red (hue 340-15):")
for c in accents(SRC / "logo.jpg", 340, 15):
    print("   ", c)
print("\nBUILDING red (hue 340-20):")
for c in accents(SRC / "arena.jpg", 340, 20):
    print("   ", c)
print("\nBUILDING greens (hue 60-160):")
for c in accents(SRC / "arena.jpg", 60, 160, min_sat=0.2):
    print("   ", c)


