"""Build a hero crop that the giant wordmark can actually sit on.

The first attempt put a 200px "Infanta" directly over the building's own
"INFANTA SPORTS ARENA" signboard: the name appeared twice and the two fought.
On a phone the crop cut the sign mid-word, which looked broken.

So: compose a taller hero canvas from the source photo where the signboard
sits low and centre, leaving clean sky at the top for the display type. Then
darken it enough for white text to hold at any size.
"""
import pathlib

from PIL import Image, ImageEnhance, ImageFilter

SRC = pathlib.Path("assets/source/arena.jpg")
OUT = pathlib.Path("static/img")
OUT.mkdir(parents=True, exist_ok=True)

b = Image.open(SRC).convert("RGB")
w, h = b.size
print("source", b.size)


def hero(target_w, target_h, name, crop_box=None, dark=0.62, blurpx=0):
    """Cover-fit a crop into target dimensions without distortion."""
    im = b.crop(crop_box) if crop_box else b.copy()
    scale = max(target_w / im.width, target_h / im.height)
    im = im.resize((max(1, round(im.width * scale)),
                    max(1, round(im.height * scale))), Image.LANCZOS)
    left = (im.width - target_w) // 2
    top = (im.height - target_h) // 2
    im = im.crop((left, top, left + target_w, top + target_h))
    if blurpx:
        im = im.filter(ImageFilter.GaussianBlur(blurpx))
    im = ImageEnhance.Brightness(im).enhance(dark)
    im = ImageEnhance.Contrast(im).enhance(1.10)
    p = OUT / name
    im.save(p, "WEBP", quality=84, method=6)
    print(f"  {name:26} {im.width}x{im.height}  {p.stat().st_size // 1024} KB")


# Desktop: wide. The whole building reads, sign centred and low, sky above
# for the wordmark to sit against.
hero(2200, 1240, "hero-wide.webp", dark=0.58)

# Phone: portrait. Letterboxing the full building into a tall frame left a
# small strip floating in a sea of black, which looked like a loading error.
# Instead, fill the frame: a blurred, darkened enlargement of the photo backs
# a sharp band of the building, so the picture reaches every edge and the
# signage still reads without being sliced mid-word.
ph_w, ph_h = 1100, 2000

bg = b.copy()
scale = max(ph_w / bg.width, ph_h / bg.height)
bg = bg.resize((round(bg.width * scale), round(bg.height * scale)), Image.LANCZOS)
left = (bg.width - ph_w) // 2
top = (bg.height - ph_h) // 2
bg = bg.crop((left, top, left + ph_w, top + ph_h))
bg = bg.filter(ImageFilter.GaussianBlur(26))
bg = ImageEnhance.Brightness(bg).enhance(0.34)

band = b.copy()
bscale = ph_w / band.width
band = band.resize((ph_w, round(band.height * bscale)), Image.LANCZOS)
band = ImageEnhance.Brightness(band).enhance(0.62)
band = ImageEnhance.Contrast(band).enhance(1.10)
# sit the building in the upper third, leaving the lower half for the wordmark
bg.paste(band, (0, int(ph_h * 0.20)))
p = OUT / "hero-phone.webp"
bg.save(p, "WEBP", quality=84, method=6)
print(f"  hero-phone.webp            {ph_w}x{ph_h}  {p.stat().st_size // 1024} KB")

# The signboard band, at its true resolution so it is never upscaled.
# The earlier version was 1190px wide stretched across a 1440px viewport
# and visibly pixelated.
sign = b.crop((int(w * 0.15), int(h * 0.24), int(w * 0.78), int(h * 0.47)))
sign = sign.resize((sign.width * 2, sign.height * 2), Image.LANCZOS)
sign.save(OUT / "arena-sign.webp", "WEBP", quality=86, method=6)
print(f"  arena-sign.webp            {sign.width}x{sign.height}  "
      f"{(OUT / 'arena-sign.webp').stat().st_size // 1024} KB")

