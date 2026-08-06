"""Render the LIVE public site in a browser and confirm it looks right.

HTTP 200 on every file does not mean the page is correct: fonts come from a
CDN here, HTTPS is enforced, and paths behave differently under a subpath
(/infanta-arena-app/) than they did on localhost.
"""
import os as _os
import sys as _sys

# Runnable from anywhere: anchor to the repository root so `import db` and the
# relative data/ and docs/ paths resolve the same way they do from the root.
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)
_os.chdir(_ROOT)

import sys

URL = "https://epatrick7th.github.io/infanta-arena-app/"
fails = []


def check(cond, msg, extra=""):
    print(("  ok   " if cond else "  FAIL ") + msg + (f"  [{extra}]" if extra else ""))
    if not cond:
        fails.append(msg)


from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch()
    for label, w, h in (("desktop", 1440, 900), ("phone", 390, 844)):
        pg = b.new_page(viewport={"width": w, "height": h})
        errors, failed = [], []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("requestfailed", lambda r: failed.append(r.url))
        pg.goto(URL, wait_until="networkidle", timeout=60000)
        pg.wait_for_timeout(2000)

        # force lazy images to load, then confirm they all decoded
        pg.evaluate("""() => document.querySelectorAll('img[loading="lazy"]')
            .forEach(i => { i.loading='eager'; const s=i.src; i.src=''; i.src=s; })""")
        try:
            pg.wait_for_function(
                "() => [...document.images].every(i => i.complete && i.naturalWidth > 0)",
                timeout=25000)
        except Exception:
            pass

        broken = pg.evaluate(
            """() => [...document.images].filter(i => !i.complete || i.naturalWidth === 0)
                     .map(i => i.src)""")
        overflow = pg.evaluate(
            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth")

        check(not broken, f"{label}: every image renders", str(broken[:2]))
        check(overflow <= 1, f"{label}: no horizontal overflow", f"{overflow}px")
        check(not errors, f"{label}: no JS errors", "; ".join(errors[:2]))
        check(not failed, f"{label}: no failed requests", "; ".join(failed[:2]))

        if label == "desktop":
            pg.screenshot(path="_live_site.png")
            print("       wrote _live_site.png")
        pg.close()

    # the GitHub link should point at the repo, not 404
    pg = b.new_page()
    pg.goto(URL, wait_until="domcontentloaded", timeout=60000)
    hrefs = pg.evaluate(
        """() => [...document.querySelectorAll('a[href^="http"]')].map(a => a.href)""")
    print("\n  external links:", sorted(set(hrefs)))
    check(any("github.com/Epatrick7th/infanta-arena-app" in h for h in hrefs),
          "links back to the repository")
    pg.close()
    b.close()

print("\n" + (f"LIVE SITE VERIFIED -> {URL}" if not fails
              else f"{len(fails)} FAILURES: {fails}"))
sys.exit(1 if fails else 0)
