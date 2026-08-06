"""Recapture the live-arena screenshot with an actual live fight.

The first capture caught an empty "No Fights Scheduled" state while the
caption on the site describes a fight in progress with betting totals. A
caption that does not match its screenshot is the kind of small dishonesty
that makes everything else on the page suspect.

Seeds a live fight with bets on both sides in a DB copy, then captures.
"""
import os
import shutil
import threading
import time
import pathlib
from datetime import date

SRC = "data/sabong.db"
TMP = "data/_live_shot.db"
shutil.copyfile(SRC, TMP)

import db as D
D.DB_PATH = TMP
import app as A

OUT = pathlib.Path("docs/screenshots")
PORT = 5098
app = A.app

threading.Thread(target=lambda: app.run(port=PORT, use_reloader=False, threaded=True),
                 daemon=True).start()
time.sleep(2.5)

from playwright.sync_api import sync_playwright

BASE = f"http://127.0.0.1:{PORT}"
today = date.today().isoformat()

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
    pg = ctx.new_page()
    pg.goto(f"{BASE}/login", wait_until="networkidle")
    pg.fill("input[name=username]", "boss_infanta")
    pg.fill("input[name=password]", "infanta123")
    pg.click("button[type=submit], input[type=submit]")
    pg.wait_for_timeout(1200)

    # create today's event, a fight, start it, and record bets both ways
    r = pg.request.post(f"{BASE}/events/new", form={
        "date": today, "name": "Saturday Derby", "event_type": "derby"})
    print("event:", r.status)

    # Use the page's own fetch() so the session cookie and origin come along.
    # pg.request is a separate context with no cookies, which is why direct
    # calls came back 403 from the ownership check.
    def api(path, payload=None, method="POST"):
        return pg.evaluate(
            """async ([path, payload, method]) => {
                const r = await fetch(path, {
                    method,
                    headers: {'Content-Type': 'application/json'},
                    credentials: 'same-origin',
                    body: payload ? JSON.stringify(payload) : undefined
                });
                let body = null;
                try { body = await r.json(); } catch (e) {}
                return {status: r.status, body};
            }""", [path, payload, method])

    import sqlite3
    con = sqlite3.connect(TMP)
    con.row_factory = sqlite3.Row
    uid = con.execute(
        "select id from users where username='boss_infanta'").fetchone()["id"]
    row = con.execute(
        "select id, boss_id, date from events where name='Saturday Derby' "
        "order by id desc limit 1").fetchone()
    print(f"logged-in boss={uid}  event={dict(row) if row else None}")
    if not row:
        raise SystemExit("event was not created")
    ev = row["id"]
    if row["boss_id"] != uid:
        raise SystemExit(f"event owned by {row['boss_id']}, not {uid}")

    r = api(f"/api/events/{ev}/fights",
            {"fight_number": 7, "meron": "Santos Gamefarm",
             "wala": "Delos Reyes Farm", "pit_fee": 1500})
    print("fight:", r)
    fid = (r.get("body") or {}).get("id")
    if not fid:
        raise SystemExit("could not create a fight; aborting rather than "
                         "shipping a screenshot that contradicts its caption")

    print("start:", api(f"/api/live-fight/{fid}/start"))
    # Amounts chosen to give an uneven, believable split. The first attempt
    # happened to total 43,500 on both sides, and a perfect 50/50 in a
    # screenshot reads as fabricated.
    for side, amt, who in (("Meron", 25000, "Ringside A"), ("Meron", 18500, "Ringside C"),
                           ("Meron", 9000, "Balcony D"),
                           ("Wala", 31000, "Ringside B"), ("Wala", 12500, "Balcony")):
        rb = api(f"/api/live-fight/{fid}/bet",
                 {"side": side, "amount": amt, "bettor_name": who})
        if rb["status"] not in (200, 201):
            print("  bet failed:", rb)
    con.close()

    pg.goto(f"{BASE}/live-arena", wait_until="networkidle")
    pg.wait_for_timeout(3000)
    # the live page polls; settle it and confirm the fight is actually shown
    shown = pg.evaluate(
        "() => document.body.innerText.includes('No Fights Scheduled')")
    print("empty-state visible:", shown)
    if shown:
        raise SystemExit("live arena still shows the empty state; not shipping "
                         "a screenshot that contradicts its caption")
    for attempt in range(3):
        try:
            pg.screenshot(path=str(OUT / "live-arena.png"), timeout=30000)
            break
        except Exception as e:
            print(f"  screenshot attempt {attempt + 1} failed: {e}")
            pg.wait_for_timeout(2000)
    else:
        raise SystemExit("could not capture the screenshot")
    print("captured live-arena.png with a live fight")
    b.close()

try:
    os.remove(TMP)
except PermissionError:
    pass

# re-optimise just this one
from PIL import Image
png = OUT / "live-arena.png"
with Image.open(png) as im:
    w, h = im.size
    im.convert("RGB").resize((w // 2, h // 2), Image.LANCZOS).save(
        OUT / "live-arena.webp", "WEBP", quality=82, method=6)
png.unlink()
print(f"live-arena.webp {(OUT / 'live-arena.webp').stat().st_size // 1024} KB")
