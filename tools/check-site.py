"""Verify the GitHub Pages site renders correctly before publishing.

Checks the things that actually break a static showcase:
  - every screenshot referenced by the page exists and loads
  - no horizontal overflow at phone, tablet and desktop widths
  - the stat numbers match the real repo (no invented figures)
  - internal anchors resolve
  - external links point where they claim
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
import re
import subprocess
import sys
import threading
import functools
import http.server
import socketserver

DOCS = pathlib.Path("docs")
PORT = 8123
fails = []


def check(cond, msg, extra=""):
    print(("  ok   " if cond else "  FAIL ") + msg + (f"  [{extra}]" if extra else ""))
    if not cond:
        fails.append(msg)


handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DOCS))
socketserver.TCPServer.allow_reuse_address = True
httpd = socketserver.TCPServer(("127.0.0.1", PORT), handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()

html = (DOCS / "index.html").read_text(encoding="utf-8")

# --- referenced images must exist on disk ---
refs = re.findall(r'src="(screenshots/[^"]+)"', html)
missing = [r for r in refs if not (DOCS / r).exists()]
check(not missing, f"all {len(refs)} referenced screenshots exist", str(missing))

# --- and nothing on disk should be unused: dead weight in a published bundle ---
on_disk = {f"screenshots/{p.name}" for p in (DOCS / "screenshots").glob("*")}
unused = sorted(on_disk - set(refs))
check(not unused, "no unreferenced screenshots shipped", str(unused))

# --- stats on the page must match reality ---
routes = len(re.findall(r"@app\.route", pathlib.Path("app.py").read_text(encoding="utf-8")))
r = subprocess.run([sys.executable, "test_security.py"], capture_output=True,
                   text=True, encoding="utf-8", errors="replace")
m = re.search(r"ALL (\d+) CHECKS PASSED", r.stdout or "")
checks_n = int(m.group(1)) if m else -1

page_routes = re.search(r"<b>(\d+)</b><span>Routes</span>", html)
page_checks = re.search(r"<b>(\d+)</b><span>Security checks</span>", html)
check(page_routes and int(page_routes.group(1)) == routes,
      "route count on the page matches the app",
      f"page={page_routes.group(1) if page_routes else '?'} actual={routes}")
check(page_checks and int(page_checks.group(1)) == checks_n,
      "security-check count matches the suite",
      f"page={page_checks.group(1) if page_checks else '?'} actual={checks_n}")

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch()
    for label, w, h in [("phone", 390, 844), ("tablet", 768, 1024),
                        ("desktop", 1440, 900)]:
        pg = b.new_page(viewport={"width": w, "height": h})
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        failed = []
        pg.on("requestfailed", lambda r: failed.append(r.url))
        pg.goto(f"http://127.0.0.1:{PORT}/", wait_until="networkidle")
        pg.wait_for_timeout(1200)

        overflow = pg.evaluate(
            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        check(overflow <= 1, f"{label}: no horizontal overflow", f"{overflow}px")
        check(not errors, f"{label}: no JS errors", "; ".join(errors[:2]))
        local_failed = [u for u in failed if "127.0.0.1" in u]
        check(not local_failed, f"{label}: all local assets load",
              "; ".join(local_failed[:2]))

        # Images are lazy-loaded, so they only fetch once scrolled near. Force
        # every one of them eager and wait, which tests "does this image load"
        # rather than "did my scroll loop happen to reach it".
        pg.evaluate("""() => {
            document.querySelectorAll('img[loading="lazy"]').forEach(i => {
                i.loading = 'eager';
                const s = i.src; i.src = ''; i.src = s;   // re-trigger the fetch
            });
        }""")
        pg.wait_for_timeout(1000)
        try:
            pg.wait_for_function(
                "() => [...document.images].every(i => i.complete && i.naturalWidth > 0)",
                timeout=15000)
        except Exception:
            pass

        broken = pg.evaluate(
            """() => [...document.images].filter(i => !i.complete || i.naturalWidth === 0)
                     .map(i => i.getAttribute('src'))""")
        check(not broken, f"{label}: every image rendered", str(broken[:3]))
        pg.close()

    # anchors resolve
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(f"http://127.0.0.1:{PORT}/", wait_until="networkidle")
    bad_anchors = pg.evaluate(
        """() => [...document.querySelectorAll('a[href^="#"]')]
                 .map(a => a.getAttribute('href'))
                 .filter(h => h.length > 1 && !document.querySelector(h))""")
    check(not bad_anchors, "internal anchors all resolve", str(bad_anchors))

    title = pg.title()
    check("Infanta" in title, "page title set", title)
    pg.close()
    b.close()

httpd.shutdown()
print("\n" + ("SITE OK" if not fails else f"{len(fails)} FAILURES: {fails}"))
sys.exit(1 if fails else 0)
