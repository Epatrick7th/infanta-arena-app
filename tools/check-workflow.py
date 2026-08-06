"""Walk the real workflows in a real browser against the RUNNING server.

Checking that pages return 200 to a scripted client is not the outcome the
user asked for. The outcome is Patrick opening a browser and using the app:
clicking through, submitting forms, creating records.

Two specific risks I have not tested against the live process:
  - the CSRF origin guard I added. Browsers send Origin on form POSTs. If I
    got that wrong, every create form silently 403s and the app is unusable.
  - Tailwind comes from a CDN, so styling could fail while HTML still 200s.

Creates real records, then deletes them, so the database is left as found.
"""
import os as _os
import sys as _sys

# Runnable from anywhere: anchor to the repository root so `import db` and the
# relative data/ and docs/ paths resolve the same way they do from the root.
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)
_os.chdir(_ROOT)

import re
import sys
import sqlite3

BASE = "http://127.0.0.1:5001"
DB = "data/sabong.db"
TAG = "BrowserWalk"
fails = []


def check(cond, msg, extra=""):
    print(("  ok   " if cond else "  FAIL ") + msg + (f"  [{extra}]" if extra else ""))
    if not cond:
        fails.append(msg)


from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    errors, failed = [], []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("requestfailed", lambda r: failed.append(f"{r.url} {r.failure}"))

    # --- 1. log in like a person ---
    pg.goto(f"{BASE}/login", wait_until="networkidle")
    check("Infanta Arena" in pg.content(), "login page renders")
    # The body is styled with a gradient, so backgroundColor is transparent
    # even when Tailwind is working; that made this check cry wolf. Test a
    # property the page actually sets, and confirm the CDN really loaded.
    styled = pg.evaluate(
        """() => {
            const s = getComputedStyle(document.body);
            return {
                image: s.backgroundImage,
                colour: s.backgroundColor,
                tw: typeof window.tailwind !== 'undefined',
            };
        }""")
    check(styled["tw"], "the Tailwind CDN script loaded")
    check(styled["image"] != "none" or
          styled["colour"] not in ("rgba(0, 0, 0, 0)", "rgb(255, 255, 255)"),
          "CSS is actually applied to the page", str(styled)[:90])

    # The assistant is the role that records data; the boss is read-only and
    # is exercised separately at the end of this walkthrough.
    pg.fill("input[name=username]", "asst_infanta")
    pg.fill("input[name=password]", "infanta_asst")
    pg.click("button[type=submit], input[type=submit]")
    pg.wait_for_load_state("networkidle")
    check("/dashboard" in pg.url, "login lands on the dashboard", pg.url)

    # --- 2. the navigation a person would click ---
    for label, path, expect in [
        ("Events", "/events", "Events"),
        ("Expenses", "/expenses", "Expenses"),
        ("Remittances", "/remittances", "Remittances"),
        ("Personnel", "/personnel", "Personnel"),
    ]:
        pg.goto(f"{BASE}{path}", wait_until="networkidle")
        check(expect in pg.content() and pg.url.endswith(path),
              f"{label} page opens", pg.url)

    # --- 3. THE REAL TEST: submit a form through the browser ---
    # This is where a broken CSRF guard would show up.
    from datetime import date
    today = date.today().isoformat()

    def fill_date(page, value):
        """Forms spell the date field differently; fill whichever exists.

        Hardcoding one name made this tool fail on a form that worked fine.
        """
        el = page.query_selector("input[type=date]") or \
            page.query_selector("input[name=date]") or \
            page.query_selector("input[name=event_date]")
        if el:
            el.fill(value)
            return True
        return False

    pg.goto(f"{BASE}/events/new", wait_until="networkidle")
    check(fill_date(pg, today), "the Create Event form has a date field")
    pg.fill("input[name=name]", f"{TAG} Derby")
    sel = pg.query_selector("select[name=event_type]")
    if sel:
        pg.select_option("select[name=event_type]", "derby")
    pg.click("button[type=submit], input[type=submit]")
    pg.wait_for_load_state("networkidle")

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    row = con.execute("select id, boss_id from events where name=?",
                      (f"{TAG} Derby",)).fetchone()
    check(row is not None, "creating an event through the browser works",
          f"landed on {pg.url}")
    if row:
        check(row["boss_id"] == 3, "the new event is owned by the arena's boss",
              f"boss_id={row['boss_id']}")

    # --- 4. an expense, the other main create form ---
    pg.goto(f"{BASE}/expenses/new", wait_until="networkidle")
    check(fill_date(pg, today), "the Create Expense form has a date field")
    pg.fill("input[name=amount]", "1234.56")
    desc = pg.query_selector("input[name=description], textarea[name=description]")
    if desc:
        desc.fill(f"{TAG} expense")
    cat = pg.query_selector("select[name=category]")
    if cat:
        opts = pg.eval_on_selector_all(
            "select[name=category] option", "els => els.map(e => e.value)")
        real = [o for o in opts if o]
        if real:
            pg.select_option("select[name=category]", real[0])
    pg.click("button[type=submit], input[type=submit]")
    pg.wait_for_load_state("networkidle")

    exp = con.execute("select id, boss_id, amount from expenses where description=?",
                      (f"{TAG} expense",)).fetchone()
    check(exp is not None, "creating an expense through the browser works")
    if exp:
        check(exp["boss_id"] == 3, "the new expense is owned by the logged-in boss")
        # It must be retrievable in the books the user then looks at. The
        # expenses page shows only the newest 60 rows and this arena's sample
        # data runs into the future, so a same-day row legitimately sits past
        # page one; ask for the row's own date rather than assuming page one.
        pg.goto(f"{BASE}/api/expenses?date_from={today}&date_to={today}",
                wait_until="networkidle")
        check(f"{TAG} expense" in pg.content(),
              "the new expense is retrievable in the owner's books")

    # --- 5. no console errors anywhere in that journey ---
    check(not errors, "no JavaScript errors during the walkthrough",
          "; ".join(errors[:2]))
    real_failed = [f for f in failed if "favicon" not in f]
    check(not real_failed, "no failed requests", "; ".join(real_failed[:2]))

    # --- 6. the boss's side: everything visible, nothing changeable ---
    # A partner should be able to read the whole book and find no control
    # that would let them alter it. Checked in a real browser because that is
    # where a leftover button would actually be clicked.
    pg.goto(f"{BASE}/logout", wait_until="networkidle")
    pg.goto(f"{BASE}/login", wait_until="networkidle")
    pg.fill("input[name=username]", "boss_infanta")
    pg.fill("input[name=password]", "infanta123")
    pg.click("button[type=submit], input[type=submit]")
    pg.wait_for_load_state("networkidle")
    check("/dashboard" in pg.url, "the boss can log in and read the books", pg.url)

    stray = []
    for path in ("/events", "/expenses", "/remittances", "/personnel",
                 "/boss/approvals"):
        pg.goto(f"{BASE}{path}", wait_until="networkidle")
        for label in ("New Event", "New Expense", "Approve", "Reject",
                      "Create Event"):
            if pg.query_selector(
                    f"a:has-text('{label}'), button:has-text('{label}')"):
                stray.append(f"{path}:{label}")
    check(not stray, "the boss is offered no control that would only fail",
          "; ".join(stray[:3]))

    pg.goto(f"{BASE}/boss/approvals", wait_until="networkidle")
    check("Created by:" in pg.content(),
          "the boss can see who recorded each pending item")

    # --- clean up: leave the database as found ---
    if row:
        con.execute("delete from events where id=?", (row["id"],))
    if exp:
        con.execute("delete from expenses where id=?", (exp["id"],))
    con.commit()
    left = con.execute(
        "select count(*) n from events where name=?", (f"{TAG} Derby",)).fetchone()["n"]
    left += con.execute(
        "select count(*) n from expenses where description=?",
        (f"{TAG} expense",)).fetchone()["n"]
    check(left == 0, "test records removed, database left as found")
    con.close()

    b.close()

print("\n" + ("BROWSER WORKFLOW OK" if not fails else f"{len(fails)} FAILURES: {fails}"))
sys.exit(1 if fails else 0)
