"""Capture real screenshots of the app for the GitHub Pages showcase.

Runs the Flask app against a COPY of the database, logs in as a boss, and
screenshots the pages worth showing. Using the real app rather than mockups
means the showcase cannot drift from what the software actually does.
"""
import os
import shutil
import sys
import threading
import time
import pathlib

SRC = "data/sabong.db"
TMP = "data/_shots.db"
shutil.copyfile(SRC, TMP)

import db as D
D.DB_PATH = TMP
import app as A

OUT = pathlib.Path("docs/screenshots")
OUT.mkdir(parents=True, exist_ok=True)

PORT = 5099
app = A.app


def serve():
    app.run(port=PORT, use_reloader=False, threaded=True)


t = threading.Thread(target=serve, daemon=True)
t.start()
time.sleep(2.5)

from playwright.sync_api import sync_playwright

BASE = f"http://127.0.0.1:{PORT}"
BOSS = ("boss_infanta", "infanta123")

# (path, filename, full page?)
PAGES = [
    ("/login", "login", False),
    ("/dashboard", "dashboard", False),
    ("/analytics", "analytics", True),
    ("/analytics/monthly", "analytics-monthly", True),
    ("/analytics/trends", "analytics-trends", True),
    ("/analytics/sales-today", "analytics-sales-today", True),
    ("/events", "events", False),
    ("/expenses", "expenses", False),
    ("/live-arena", "live-arena", False),
    ("/boss/approvals", "approvals", False),
]

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 900},
                        device_scale_factor=2)
    pg = ctx.new_page()

    # login page first, before authenticating
    pg.goto(f"{BASE}/login", wait_until="networkidle")
    pg.wait_for_timeout(600)
    pg.screenshot(path=str(OUT / "login.png"))
    print("  ok  login.png")

    pg.fill("input[name=username]", BOSS[0])
    pg.fill("input[name=password]", BOSS[1])
    pg.click("button[type=submit], input[type=submit]")
    pg.wait_for_timeout(1200)

    for path, name, full in PAGES[1:]:
        try:
            pg.goto(f"{BASE}{path}", wait_until="networkidle")
            pg.wait_for_timeout(1500)  # let counters/animations settle
            pg.screenshot(path=str(OUT / f"{name}.png"), full_page=full)
            print(f"  ok  {name}.png")
        except Exception as e:
            print(f"  !! {name}: {e}")

    # a phone-width shot of the dashboard, since the audience is mobile-first
    mob = b.new_context(viewport={"width": 390, "height": 844},
                        device_scale_factor=2)
    mp = mob.new_page()
    mp.goto(f"{BASE}/login", wait_until="networkidle")
    mp.fill("input[name=username]", BOSS[0])
    mp.fill("input[name=password]", BOSS[1])
    mp.click("button[type=submit], input[type=submit]")
    mp.wait_for_timeout(1200)
    mp.goto(f"{BASE}/dashboard", wait_until="networkidle")
    mp.wait_for_timeout(1200)
    mp.screenshot(path=str(OUT / "dashboard-mobile.png"))
    print("  ok  dashboard-mobile.png")

    b.close()

try:
    os.remove(TMP)
except PermissionError:
    pass

shots = sorted(OUT.glob("*.png"))
total = sum(f.stat().st_size for f in shots)
print(f"\n{len(shots)} screenshots, {total/1e6:.1f} MB -> {OUT}")
