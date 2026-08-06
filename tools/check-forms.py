"""Fill in every data-entry form in a browser and confirm the values persist.

Not "does it return 200" but "did what the user typed reach the database".
The silent-discard bugs would pass a status-code check while losing a staff
member's pay rate.

Creates records, verifies each typed value, then removes them.
"""
import os as _os
import sys as _sys

# Runnable from anywhere: anchor to the repository root so `import db` and the
# relative data/ and docs/ paths resolve the same way they do from the root.
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)
_os.chdir(_ROOT)

import sqlite3
import sys
from datetime import date

BASE = "http://127.0.0.1:5001"
DB = "data/sabong.db"
TAG = "FormWalk"
today = date.today().isoformat()
fails = []


def check(cond, msg, extra=""):
    print(("  ok   " if cond else "  FAIL ") + msg + (f"  [{extra}]" if extra else ""))
    if not cond:
        fails.append(msg)


con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
created = []

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(f"{BASE}/login", wait_until="networkidle")
    pg.fill("input[name=username]", "boss_infanta")
    pg.fill("input[name=password]", "infanta123")
    pg.click("button[type=submit], input[type=submit]")
    pg.wait_for_load_state("networkidle")

    # ---------- EVENT ----------
    print("Create Event:")
    pg.goto(f"{BASE}/events/new", wait_until="networkidle")
    pg.fill("input[name=name]", f"{TAG} Derby")
    pg.fill("input[name=event_date]", today)
    pg.select_option("select[name=event_type]", "tournament")
    pg.fill("input[name=location]", "Ringside B")
    pg.fill("textarea[name=notes]", "typed by the walkthrough")
    pg.click("button[type=submit], input[type=submit]")
    pg.wait_for_load_state("networkidle")

    row = con.execute("select * from events where name=?", (f"{TAG} Derby",)).fetchone()
    check(row is not None, "the event is created")
    if row:
        created.append(("events", row["id"]))
        check(row["date"] == today, "the date the user picked was saved", row["date"])
        check(row["event_type"] == "tournament", "the event type was saved",
              row["event_type"])
        check(row["location"] == "Ringside B", "the location was saved", row["location"])
        check(row["note"] == "typed by the walkthrough", "the note was saved",
              str(row["note"]))
        check(row["boss_id"] == 3, "owned by the logged-in partner")

    # ---------- EXPENSE ----------
    print("\nCreate Expense:")
    pg.goto(f"{BASE}/expenses/new", wait_until="networkidle")
    pg.fill("input[name=date]", today)
    pg.fill("input[name=amount]", "4321.99")
    pg.fill("input[name=description]", f"{TAG} expense")
    opts = pg.eval_on_selector_all("select[name=category] option",
                                   "els => els.map(e => e.value)")
    real = [o for o in opts if o]
    if real:
        pg.select_option("select[name=category]", real[0])
    pg.click("button[type=submit], input[type=submit]")
    pg.wait_for_load_state("networkidle")

    row = con.execute("select * from expenses where description=?",
                      (f"{TAG} expense",)).fetchone()
    check(row is not None, "the expense is created")
    if row:
        created.append(("expenses", row["id"]))
        check(abs(row["amount"] - 4321.99) < 0.01, "the amount was saved", row["amount"])
        check(row["boss_id"] == 3, "owned by the logged-in partner")

    # ---------- REMITTANCE ----------
    print("\nCreate Remittance:")
    pg.goto(f"{BASE}/remittances/new", wait_until="networkidle")
    pg.fill("input[name=date]", today)
    pg.fill("input[name=amount]", "5000")
    rec = pg.query_selector("input[name=recipient]")
    if rec:
        rec.fill(f"{TAG} recipient")
    nt = pg.query_selector("textarea[name=notes], input[name=notes]")
    if nt:
        nt.fill("remittance note")
    pg.click("button[type=submit], input[type=submit]")
    pg.wait_for_load_state("networkidle")

    row = con.execute(
        "select * from cash_remittances where note like ? order by id desc limit 1",
        (f"%{TAG}%",)).fetchone()
    check(row is not None, "the remittance is created and kept the typed text")
    if row:
        created.append(("cash_remittances", row["id"]))
        check("remittance note" in (row["note"] or ""),
              "the note the user typed was saved", str(row["note"]))

    # ---------- PERSONNEL ----------
    print("\nAdd Personnel:")
    pg.goto(f"{BASE}/personnel/new", wait_until="networkidle")
    pg.fill("input[name=name]", f"{TAG} Handler")
    popts = pg.eval_on_selector_all("select[name=position] option",
                                    "els => els.map(e => e.value)")
    preal = [o for o in popts if o]
    if preal:
        pg.select_option("select[name=position]", preal[0])
    rate = pg.query_selector("input[name=daily_rate], input[name=rate]")
    if rate:
        rate.fill("750")
    pg.click("button[type=submit], input[type=submit]")
    pg.wait_for_load_state("networkidle")

    row = con.execute("select * from personnel where name=?",
                      (f"{TAG} Handler",)).fetchone()
    check(row is not None, "the staff member is created")
    if row:
        created.append(("personnel", row["id"]))
        check(row["rate_per_shift"] == 750,
              "the pay rate was saved (was silently discarded before)",
              str(row["rate_per_shift"]))
        check(row["boss_id"] == 3, "owned by the logged-in partner")

    b.close()

# ---------- leave the database as found ----------
for table, rid in created:
    con.execute(f"delete from {table} where id=?", (rid,))
con.commit()
left = sum(con.execute(f"select count(*) from {t} where id=?", (i,)).fetchone()[0]
           for t, i in created)
check(left == 0, "test records removed, database left as found")
con.close()

print("\n" + ("ALL FORMS WORK END TO END" if not fails
              else f"{len(fails)} FAILURES: {fails}"))
sys.exit(1 if fails else 0)
