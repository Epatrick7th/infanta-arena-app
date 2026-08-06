"""Prepare Patrick's two images for the web.

Two source files have to carry an entire long-scroll page, so I derive
several crops and treatments from them rather than repeating the same
picture. All from the originals, nothing invented.
"""
import pathlib

from PIL import Image, ImageEnhance

SRC = pathlib.Path("assets/source")
OUT = pathlib.Path("static/img")
OUT.mkdir(parents=True, exist_ok=True)


def save(im, name, width=None, quality=82):
    if width and im.width > width:
        im = im.resize((width, round(im.height * width / im.width)),
                       Image.LANCZOS)
    p = OUT / name
    im.convert("RGB").save(p, "WEBP", quality=quality, method=6)
    print(f"  {name:28} {im.width}x{im.height}  {p.stat().st_size // 1024} KB")


# ---- the building ----------------------------------------------------
b = Image.open(SRC / "arena.jpg").convert("RGB")
print("building", b.size)
save(b, "arena-wide.webp", 2000)

# the facade and signage, cropped tight, for a portrait-ish panel.
# the first attempt cut the word ARENA in half, so this keeps the whole sign
w, h = b.size
save(b.crop((int(w * 0.13), int(h * 0.08), int(w * 0.78), int(h * 0.92))),
     "arena-facade.webp", 1200)
# the signboard alone
save(b.crop((int(w * 0.15), int(h * 0.24), int(w * 0.76), int(h * 0.46))),
     "arena-sign.webp", 1600)
# the setting: fields and trees to the right. Starting this crop at 30% of
# the height caught the tail of the signboard, so a stray half-word "NA"
# floated in the corner. Start below the sign instead.
save(b.crop((int(w * 0.62), int(h * 0.44), w, int(h * 0.98))),
     "arena-setting.webp", 1200)

# the roofline against the sky, a quiet horizontal for breathing room
save(b.crop((0, 0, w, int(h * 0.30))), "arena-roofline.webp", 2000)

# ---- the logo --------------------------------------------------------
lg = Image.open(SRC / "logo.jpg").convert("RGB")
print("logo", lg.size)
save(lg, "logo.webp", 900, quality=88)
save(lg, "logo-sm.webp", 320, quality=88)

# the illustrated cockfight inside the crest, cropped out of the badge,
# for a full-bleed band
lw, lh = lg.size
save(lg.crop((int(lw * 0.10), int(lh * 0.10), int(lw * 0.90), int(lh * 0.60))),
     "logo-scene.webp", 1400, quality=86)

print("\ndone ->", OUT.resolve())



