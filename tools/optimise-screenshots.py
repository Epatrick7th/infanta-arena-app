"""Shrink the screenshots for the web.

Captured at device_scale_factor=2 for sharpness on retina displays, which is
right for quality and wrong for a 13 MB page. Halve them back to CSS pixels
and re-encode as WebP, which typically lands under a tenth of the PNG size
with no visible loss at display size.

Keeps the PNGs out of the published bundle entirely; docs/ ships WebP only.
"""
import os as _os
import sys as _sys

# Runnable from anywhere: anchor to the repository root so `import db` and the
# relative data/ and docs/ paths resolve the same way they do from the root.
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)
_os.chdir(_ROOT)

import pathlib
import sys

from PIL import Image

SRC = pathlib.Path("docs/screenshots")
before = after = 0
rows = []

for png in sorted(SRC.glob("*.png")):
    with Image.open(png) as im:
        w, h = im.size
        # captured at 2x; step down to the CSS size we actually display
        im = im.convert("RGB").resize((w // 2, h // 2), Image.LANCZOS)
        webp = png.with_suffix(".webp")
        im.save(webp, "WEBP", quality=82, method=6)
    b, a = png.stat().st_size, webp.stat().st_size
    before += b
    after += a
    rows.append((png.name, b / 1024, a / 1024, w // 2, h // 2))
    png.unlink()  # ship WebP only

for name, b, a, w, h in rows:
    print(f"  {name:28} {b:7.0f} KB -> {a:6.0f} KB   {w}x{h}")

print(f"\ntotal {before/1e6:.1f} MB -> {after/1e6:.2f} MB "
      f"({100 * (1 - after / before):.0f}% smaller)")
if after > 2_000_000:
    print("still over 2 MB; consider dropping a screenshot")
    sys.exit(1)
