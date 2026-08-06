"""Verify the static Pages build, served the way GitHub Pages will serve it.

Checking that files exist proves nothing: the real risks are a broken
relative path, a link pointing at a Flask route that does not exist on a
static host, or a page that renders differently from the one Patrick
approved. So this serves docs/ over plain HTTP and drives it in a browser.
"""
import functools
import http.server
import pathlib
import socketserver
import sys
import threading

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
PORT = 8919
fails = []


def check(cond, msg, extra=""):
    print(("  ok   " if cond else "  FAIL ") + msg + (f"  [{extra}]" if extra else ""))
    if not cond:
        fails.append(msg)


Handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                            directory=str(DOCS))


class Quiet(socketserver.TCPServer):
    allow_reuse_address = True


httpd = Quiet(("127.0.0.1", PORT), Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{PORT}"
print(f"serving docs/ at {BASE}\n")

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    errors, failed = [], []
    pg.on("console", lambda m: m.type == "error" and errors.append(m.text))
    pg.on("requestfailed",
          lambda r: failed.append(r.url.split("/")[-1]))
    bad_status = []
    pg.on("response", lambda r: r.status >= 400 and bad_status.append(
        f"{r.url.split('/')[-1]} -> {r.status}"))

    pg.goto(BASE + "/", wait_until="networkidle", timeout=60000)
    pg.wait_for_timeout(2500)

    # it must be the v4 page, not the old developer showcase
    title = pg.title()
    check("Infanta Sports Arena" in title, "the site root serves the v4 page", title)
    check(pg.locator("#tellers").count() == 1, "the tellers section is present")
    check(pg.locator("#journey").count() == 1, "the road section is present")
    check(pg.locator("#coast").count() == 1, "the coast section is present")

    # every asset must resolve on a static host
    broken = pg.evaluate("""() => [...document.images]
        .filter(i => !i.complete || i.naturalWidth === 0)
        .map(i => i.getAttribute('src'))""")
    check(not broken, "every image resolves over plain HTTP", "; ".join(broken[:4]))
    check(not bad_status, "no 404s on any request", "; ".join(bad_status[:4]))
    check(not [f for f in failed if "favicon" not in f],
          "no failed requests", "; ".join(failed[:3]))
    check(not errors, "no console errors", "; ".join(errors[:2]))

    # no link may point at a Flask route that does not exist here
    hrefs = pg.evaluate("""() => [...document.querySelectorAll('a[href]')]
        .map(a => a.getAttribute('href'))""")
    flasky = [h for h in hrefs
              if h.startswith("/") and not h.startswith("//")]
    check(not flasky, "no links point at server-only routes", "; ".join(flasky[:4]))

    # every internal link must actually resolve, not merely look relative
    import urllib.error
    import urllib.request
    dead = []
    for h in {h for h in hrefs if h and not h.startswith(("#", "http", "mailto:", "tel:"))}:
        try:
            with urllib.request.urlopen(BASE + "/" + h.lstrip("/"), timeout=5) as resp:
                if resp.status >= 400:
                    dead.append(f"{h} -> {resp.status}")
        except urllib.error.HTTPError as e:
            dead.append(f"{h} -> {e.code}")
        except Exception as e:
            dead.append(f"{h} -> {type(e).__name__}")
    check(not dead, "every internal link resolves", "; ".join(dead[:4]))

    # the animations must still run in the static build
    pg.wait_for_timeout(500)
    counts = pg.evaluate("""() => [...document.querySelectorAll('.board [data-count]')]
        .map(e => e.textContent.trim())""")
    check(all(c not in ("0", "") for c in counts),
          "the board still counts up in the static build", str(counts))
    widths = pg.evaluate("""() => [...document.querySelectorAll('.bar i')]
        .map(i => Math.round(i.getBoundingClientRect().width /
             i.parentElement.getBoundingClientRect().width * 100))""")
    check(sum(widths) >= 98, "the meron/wala bars render", str(widths))

    # the schedule must have survived the bake
    rows = pg.locator(".row").count()
    check(rows > 0, "the fight schedule is baked into the static page",
          f"{rows} rows")

    # phone
    ph = b.new_page(viewport={"width": 390, "height": 844})
    ph.goto(BASE + "/", wait_until="networkidle", timeout=60000)
    ph.wait_for_timeout(1500)
    of = ph.evaluate("""() => {
        const w = document.documentElement.clientWidth;
        return [...document.querySelectorAll('*')]
          .filter(el => el.getBoundingClientRect().right > w + 2).length;
    }""")
    check(of == 0, "phone: nothing overflows", f"{of} elements")

    # the old developer showcase must still work at its new home
    r2 = pg.goto(BASE + "/system/", wait_until="networkidle", timeout=60000)
    check(r2 is not None and r2.status < 400,
          "the previous project site still works at /system/",
          str(r2.status if r2 else "no response"))
    # that page lazy-loads its screenshots, so scroll the whole way before
    # judging them: an unloaded image is not a broken one
    h = pg.evaluate("() => document.body.scrollHeight")
    for frac in [i / 10 for i in range(11)]:
        pg.evaluate(f"() => window.scrollTo(0, {int(h * frac)})")
        pg.wait_for_timeout(180)
    pg.wait_for_timeout(900)
    sys_broken = pg.evaluate("""() => [...document.images]
        .filter(i => !i.complete || i.naturalWidth === 0).length""")
    check(sys_broken == 0, "/system/ images still resolve", f"{sys_broken} broken")

    b.close()

httpd.shutdown()
print("\n" + ("STATIC SITE OK" if not fails else f"{len(fails)} FAILURES: {fails}"))
sys.exit(1 if fails else 0)
