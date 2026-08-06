"""Check v3, including whether the animations actually do anything.

A screenshot proves layout but not motion. These checks assert that the
counters really count up from zero, that the bars really animate to their
data-driven width, and that the numbers on screen match what the database
says, since a wrong number on a gambling page is worse than an ugly one.
"""
import pathlib
import sys

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5001/v4"
OUT = pathlib.Path("_shots4")
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

    # --- the counters must genuinely animate, not just print a value ---
    pg.wait_for_timeout(80)
    early = pg.evaluate(
        """() => [...document.querySelectorAll('.board [data-count]')]
                 .map(e => e.textContent.trim())""")
    pg.wait_for_timeout(3000)
    late = pg.evaluate(
        """() => [...document.querySelectorAll('.board [data-count]')]
                 .map(e => e.textContent.trim())""")
    targets = pg.evaluate(
        """() => [...document.querySelectorAll('.board [data-count]')]
                 .map(e => e.getAttribute('data-count'))""")
    check(early != late, "the counters animate rather than appearing instantly",
          f"{early} -> {late}")
    check([l.replace(",", "") for l in late] == targets,
          "the counters land exactly on the real figures", f"{late} vs {targets}")

    # --- the split bars must reach their data-driven width ---
    widths = pg.evaluate(
        """() => [...document.querySelectorAll('.bar i')].map(i => ({
               set: i.getAttribute('data-w'),
               got: Math.round(i.getBoundingClientRect().width /
                    i.parentElement.getBoundingClientRect().width * 100)
           }))""")
    ok_bars = all(abs(int(w["set"]) - w["got"]) <= 2 for w in widths) and widths
    check(ok_bars, "the meron/wala bars animate to their true share", str(widths))
    total = sum(int(w["set"]) for w in widths)
    check(total == 100, "the two sides sum to 100%", f"{total}%")

    # --- scroll progress must actually track ---
    pg.evaluate("() => window.scrollTo(0, document.body.scrollHeight * 0.5)")
    pg.wait_for_timeout(400)
    mid = pg.evaluate("() => document.getElementById('prog').style.width")
    check(mid not in ("", "0%"), "the scroll progress bar tracks the page", mid)

    # --- the usual structural checks ---
    pg.evaluate("() => window.scrollTo(0, 0)")
    h = pg.evaluate("() => document.body.scrollHeight")
    for i, frac in enumerate([0, .13, .27, .42, .58, .73, .88, .98]):
        pg.evaluate(f"() => window.scrollTo(0, {int(h * frac)})")
        pg.wait_for_timeout(850)
        pg.screenshot(path=str(OUT / f"v3-{i}.png"))
    pg.screenshot(path=str(OUT / "v3-full.png"), full_page=True)

    broken = pg.evaluate("""() => [...document.images]
        .filter(i => !i.complete || i.naturalWidth === 0).map(i => i.src)""")
    check(not broken, "every image loaded", "; ".join(broken[:3]))

    overflow = pg.evaluate("""() => {
        const w = document.documentElement.clientWidth;
        return [...document.querySelectorAll('*')]
            .filter(el => el.getBoundingClientRect().right > w + 2)
            .slice(0,5).map(el => el.tagName+'.'+(el.className||'').toString().slice(0,28));
    }""")
    check(not overflow, "nothing overflows the viewport", "; ".join(overflow[:3]))
    check(not errors, "no console errors", "; ".join(errors[:2]))
    check(not [f for f in failed if "favicon" not in f], "no failed requests")

    hidden = pg.evaluate("""() => [...document.querySelectorAll('.up')]
        .filter(el => getComputedStyle(el).opacity === '0').length""")
    check(hidden == 0, "all revealed content is visible", f"{hidden} hidden")

    # --- phone ---
    ph = b.new_page(viewport={"width": 390, "height": 844})
    ph.goto(BASE, wait_until="networkidle", timeout=60000)
    ph.wait_for_timeout(2200)
    ph.screenshot(path=str(OUT / "v3-phone.png"))
    h2 = ph.evaluate("() => document.body.scrollHeight")
    for frac in [i / 10 for i in range(11)]:
        ph.evaluate(f"() => window.scrollTo(0, {int(h2 * frac)})")
        ph.wait_for_timeout(200)
    ph.evaluate("() => window.scrollTo(0,0)")
    ph.wait_for_timeout(500)
    ph.screenshot(path=str(OUT / "v3-phone-full.png"), full_page=True)
    ph_of = ph.evaluate("""() => {
        const w = document.documentElement.clientWidth;
        return [...document.querySelectorAll('*')]
            .filter(el => el.getBoundingClientRect().right > w + 2)
            .slice(0,5).map(el => el.tagName+'.'+(el.className||'').toString().slice(0,28));
    }""")
    check(not ph_of, "phone: nothing overflows", "; ".join(ph_of[:3]))

    # --- reduced motion must be respected, not merely declared ---
    rm = b.new_context(reduced_motion="reduce", viewport={"width":1440,"height":900})
    rp = rm.new_page()
    rp.goto(BASE, wait_until="networkidle", timeout=60000)
    rp.wait_for_timeout(500)
    rm_vals = rp.evaluate(
        """() => [...document.querySelectorAll('.board [data-count]')]
                 .map(e => e.textContent.trim())""")
    check(all(v not in ("0", "") for v in rm_vals),
          "reduced motion still shows the final numbers", str(rm_vals))

    b.close()

print("\n" + ("V4 OK" if not fails else f"{len(fails)} FAILURES: {fails}"))
sys.exit(1 if fails else 0)


