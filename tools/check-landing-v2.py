"""Look at the landing page the way a visitor would.

Screenshots at several scroll depths and on a phone, because a long-scroll
page cannot be judged from markup or a 200 response. Also collect anything
that would embarrass us: console errors, failed image requests, and elements
spilling outside the viewport.
"""
import pathlib
import sys

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5001/v2"
OUT = pathlib.Path("_shots2")
OUT.mkdir(exist_ok=True)

fails = []


def check(cond, msg, extra=""):
    print(("  ok   " if cond else "  FAIL ") + msg + (f"  [{extra}]" if extra else ""))
    if not cond:
        fails.append(msg)


with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    errors, failed = [], []
    pg.on("console", lambda m: m.type == "error" and errors.append(m.text))
    pg.on("requestfailed",
          lambda r: failed.append(f"{r.url.split('/')[-1]}: {r.failure}"))

    pg.goto(BASE, wait_until="networkidle", timeout=60000)
    pg.wait_for_timeout(1200)

    height = pg.evaluate("() => document.body.scrollHeight")
    print("page height:", height)

    pg.screenshot(path=str(OUT / "land-full.png"), full_page=True)
    for i, frac in enumerate([0, .12, .26, .40, .55, .70, .85, .97]):
        pg.evaluate(f"() => window.scrollTo(0, {int(height * frac)})")
        pg.wait_for_timeout(900)
        pg.screenshot(path=str(OUT / f"land{i}.png"))

    # every image must actually have loaded, not just be referenced
    broken = pg.evaluate("""() => [...document.images]
        .filter(i => !i.complete || i.naturalWidth === 0)
        .map(i => i.currentSrc || i.src)""")
    check(not broken, "every image loaded", "; ".join(broken[:3]))

    # nothing may overflow horizontally: the classic long-scroll bug
    overflow = pg.evaluate("""() => {
        const w = document.documentElement.clientWidth;
        return [...document.querySelectorAll('*')]
            .filter(el => el.getBoundingClientRect().right > w + 2)
            .slice(0, 5)
            .map(el => el.tagName + '.' + (el.className || '').toString().slice(0, 30));
    }""")
    check(not overflow, "nothing overflows the viewport width",
          "; ".join(overflow[:3]))

    check(not errors, "no console errors", "; ".join(errors[:2]))
    real = [f for f in failed if "favicon" not in f]
    check(not real, "no failed requests", "; ".join(real[:2]))

    # the reveal animation must finish, or content stays invisible
    hidden = pg.evaluate("""() => {
        window.scrollTo(0, document.body.scrollHeight);
        return [...document.querySelectorAll('.rise')]
            .filter(el => getComputedStyle(el).opacity === '0').length;
    }""")
    pg.wait_for_timeout(1600)
    hidden_after = pg.evaluate("""() => [...document.querySelectorAll('.rise')]
        .filter(el => getComputedStyle(el).opacity === '0').length""")
    check(hidden_after == 0, "all revealed content becomes visible",
          f"{hidden_after} still hidden")

    # phone
    ph = b.new_page(viewport={"width": 390, "height": 844})
    ph.goto(BASE, wait_until="networkidle", timeout=60000)
    ph.wait_for_timeout(1200)
    ph.screenshot(path=str(OUT / "land-phone-top.png"))
    ph.screenshot(path=str(OUT / "land-phone-full.png"), full_page=True)
    ph_overflow = ph.evaluate("""() => {
        const w = document.documentElement.clientWidth;
        return [...document.querySelectorAll('*')]
            .filter(el => el.getBoundingClientRect().right > w + 2)
            .slice(0, 5)
            .map(el => el.tagName + '.' + (el.className || '').toString().slice(0, 30));
    }""")
    check(not ph_overflow, "phone: nothing overflows", "; ".join(ph_overflow[:3]))
    check(ph.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 2"),
          "phone: no horizontal scroll")

    b.close()

print("\n" + ("LANDING PAGE OK" if not fails else f"{len(fails)} FAILURES: {fails}"))
sys.exit(1 if fails else 0)

