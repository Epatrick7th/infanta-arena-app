"""Security and regression suite for the Infanta Arena app.

Run:  python test_security.py

Covers the defects found on 2026-08-05, so they cannot come back:

  1. anonymous access      every non-public route redirects to /login
  2. list isolation        a boss sees only their own events/expenses/remittances
  3. IDOR                  a boss cannot read or mutate another boss's records
  4. write ownership       new rows are stamped with the creating boss
  5. assistant scoping     an assistant resolves to their arena's boss
  6. JSON coercion         the write APIs accept JSON numbers and strings
  7. no 5xx                every GET page loads for boss and assistant

Everything that writes runs against a throwaway copy of the database, so the
real data is never touched.
"""
import os
import shutil
import sqlite3
import sys
from datetime import date

REAL_DB = "data/sabong.db"
TMP_DB = "data/_test_security.db"

BOSS = ("boss_infanta", "infanta123")
BOSS2 = ("boss_royal", "royal123")
ASSISTANT = ("asst_infanta", "infanta_asst")

failures = []
checks = 0


def check(cond, msg, extra=""):
    global checks
    checks += 1
    print(("  ok   " if cond else "  FAIL ") + msg + (f"  [{extra}]" if extra else ""))
    if not cond:
        failures.append(msg)


def section(title):
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def login(client, creds):
    client.post("/login", data={"username": creds[0], "password": creds[1]})
    with client.session_transaction() as s:
        return s.get("user_id")


# --- work on a copy -------------------------------------------------------
shutil.copyfile(REAL_DB, TMP_DB)
import db as D
D.DB_PATH = TMP_DB
import app as A

app = A.app
app.config["TESTING"] = True
con = sqlite3.connect(TMP_DB)
con.row_factory = sqlite3.Row


# =========================================================== 1. anonymous ==
section("1. Anonymous access is refused")
PUBLIC = {"login", "register", "home", "static", "logout"}
SAMPLE = {"event_id": "1", "expense_id": "1", "remittance_id": "1",
          "revenue_id": "1", "fight_id": "1", "roster_id": "1",
          "username": "boss_infanta", "category": "payroll",
          "sales_type": "plasada", "filename": "style.css"}
leaks = 0
with app.test_client() as c:
    for r in app.url_map.iter_rules():
        if r.endpoint in PUBLIC:
            continue
        for m in sorted(r.methods - {"HEAD", "OPTIONS"}):
            url = r.build({k: SAMPLE.get(k, "1") for k in r.arguments})[1]
            resp = c.open(url, method=m)
            if not (resp.status_code in (301, 302, 303) and
                    "login" in resp.headers.get("Location", "").lower()):
                leaks += 1
                print(f"       reachable: {m} {url} -> {resp.status_code}")
check(leaks == 0, "every protected route redirects anonymous users to /login",
      f"{leaks} reachable")


# ====================================================== 2. list isolation ==
section("2. List endpoints show only the caller's own rows")
with app.test_client() as c:
    uid = login(c, BOSS)
    for url, table, label in (("/api/events", "events", "events"),
                              ("/api/expenses", "expenses", "expenses"),
                              ("/api/remittances", "cash_remittances", "remittances")):
        payload = c.get(url).get_json()
        items = payload if isinstance(payload, list) else payload.get("rows", [])
        owned = con.execute(
            f"select count(*) n from {table} where boss_id=? and deleted_at is null",
            (uid,)).fetchone()["n"]
        foreign = [i for i in items if i.get("boss_id") != uid]
        check(not foreign and len(items) == owned,
              f"{label}: returns only my {owned} rows",
              f"got {len(items)}, foreign {len(foreign)}")


# ================================================================ 3. IDOR ==
section("3. One boss cannot touch another boss's records")
with app.test_client() as c:
    uid = login(c, BOSS)
    victim = con.execute(
        "select boss_id from events where boss_id <> ? limit 1", (uid,)).fetchone()["boss_id"]
    ev = con.execute("select id from events where boss_id=? limit 1", (victim,)).fetchone()["id"]
    fi = con.execute("select id from fights where boss_id=? limit 1", (victim,)).fetchone()["id"]

    r = c.get(f"/events/{ev}")
    check(r.status_code in (302, 403, 404), "cannot view another boss's event",
          f"-> {r.status_code}")
    r = c.open(f"/api/fights/{fi}", method="PUT", json={"winner": "Meron"})
    check(r.status_code in (403, 404), "cannot edit another boss's fight", f"-> {r.status_code}")
    r = c.open(f"/api/fights/{fi}", method="DELETE")
    check(r.status_code in (403, 404), "cannot delete another boss's fight", f"-> {r.status_code}")
    r = c.post(f"/api/events/{ev}/fights",
               json={"fight_number": 1, "meron": "X", "wala": "Y"})
    check(r.status_code in (403, 404), "cannot add a fight to another boss's event",
          f"-> {r.status_code}")
    r = c.post(f"/api/events/{ev}/revenue", json={"source": "gate", "amount": 10})
    check(r.status_code in (403, 404), "cannot add revenue to another boss's event",
          f"-> {r.status_code}")

    # and the flip side: own records still work
    own_ev = con.execute("select id from events where boss_id=? limit 1", (uid,)).fetchone()
    check(c.get(f"/events/{own_ev['id']}").status_code == 200,
          "can still view my own event")


# =================================================== 4. write ownership ====
section("4. New rows are stamped with the creating boss")
with app.test_client() as c:
    uid = login(c, BOSS2)
    today = date.today().isoformat()
    tag = "SecuritySuite"

    c.post("/events/new", data={"date": today, "name": tag, "event_type": "derby"})
    ev = con.execute("select id, boss_id from events where name=?", (tag,)).fetchone()
    check(ev and ev["boss_id"] == uid, "event records its owner",
          f"boss_id={ev['boss_id'] if ev else None} want {uid}")

    c.post("/expenses/new", data={"date": today, "amount": "50",
                                  "description": tag, "category": "supplies"})
    row = con.execute("select boss_id from expenses where description=?", (tag,)).fetchone()
    check(row and row["boss_id"] == uid, "expense records its owner")

    c.post("/remittances/new", data={"date": today, "amount": "50", "note": tag})
    row = con.execute("select boss_id from cash_remittances where note=?", (tag,)).fetchone()
    check(row and row["boss_id"] == uid, "remittance records its owner")

    if ev:
        c.post(f"/api/events/{ev['id']}/fights",
               json={"fight_number": 1, "meron": "A", "wala": "B"})
        row = con.execute("select boss_id from fights where event_id=?", (ev["id"],)).fetchone()
        check(row and row["boss_id"] == uid, "fight records its owner")

        c.post(f"/api/events/{ev['id']}/revenue", json={"source": "gate", "amount": 10})
        row = con.execute(
            "select boss_id from event_revenue where event_id=?", (ev["id"],)).fetchone()
        check(row and row["boss_id"] == uid, "revenue records its owner")

    # personnel and the shift roster share the same ownership rule
    c.post("/personnel/new", data={"name": tag, "position": "Handler",
                                   "date_hired": today, "rate": "500"})
    person = con.execute(
        "select id, boss_id from personnel where name=?", (tag,)).fetchone()
    check(person and person["boss_id"] == uid, "personnel records its owner",
          f"boss_id={person['boss_id'] if person else None} want {uid}")

    shift = con.execute("select id from shift_types limit 1").fetchone()
    if shift is None:
        # the roster feature needs at least one shift type; seed one on the
        # copy so ownership is genuinely exercised rather than silently skipped
        con.execute("INSERT INTO shift_types (name, start_time, end_time) "
                    "VALUES ('Test Shift', '08:00', '16:00')")
        con.commit()
        shift = con.execute("select id from shift_types limit 1").fetchone()
    if person and shift:
        r = c.post("/api/shift-roster",
                   json={"date": today, "shift_type_id": shift["id"],
                         "personnel_id": person["id"]})
        check(r.status_code in (200, 201), "roster entry accepted",
              f"-> {r.status_code}")
        row = con.execute(
            "select boss_id from shift_roster where personnel_id=?",
            (person["id"],)).fetchone()
        check(row and row["boss_id"] == uid, "roster entry records its owner")
    else:
        print("       (no shift_types rows, roster ownership not exercised)")


# ==================================================== 5. assistant scope ===
section("5. Assistants see their own arena, and only theirs")
with app.test_client() as c:
    if login(c, ASSISTANT) is None:
        check(False, "assistant can log in")
    else:
        boss = con.execute(
            "select id from users where username='boss_infanta'").fetchone()["id"]
        payload = c.get("/api/events").get_json()
        items = payload if isinstance(payload, list) else payload.get("rows", [])
        foreign = [i for i in items if i.get("boss_id") != boss]
        want = con.execute(
            "select count(*) n from events where boss_id=? and deleted_at is null",
            (boss,)).fetchone()["n"]
        check(not foreign and len(items) == want,
              "assistant sees exactly their boss's events",
              f"got {len(items)} want {want}, foreign {len(foreign)}")


# ==================================================== 6. JSON coercion =====
section("6. JSON write APIs accept numbers and numeric strings")
with app.test_client() as c:
    uid = login(c, BOSS)
    ev = con.execute("select id from events where boss_id=? limit 1", (uid,)).fetchone()["id"]

    r = c.post(f"/api/events/{ev}/revenue", json={"source": "gate", "amount": 1500})
    check(r.status_code == 201, "revenue accepts a JSON number", f"-> {r.status_code}")
    r = c.post(f"/api/events/{ev}/revenue", json={"source": "gate", "amount": "1500.25"})
    check(r.status_code == 201, "revenue accepts a numeric string", f"-> {r.status_code}")
    r = c.post(f"/api/events/{ev}/revenue", json={"source": "gate", "amount": "abc"})
    check(r.status_code == 400, "revenue rejects a non-numeric amount", f"-> {r.status_code}")

    r = c.post(f"/api/events/{ev}/fights",
               json={"fight_number": "7", "meron": "A", "wala": "B", "pit_fee": "250.50"})
    check(r.status_code == 201, "fight accepts numeric strings", f"-> {r.status_code}")
    r = c.post(f"/api/events/{ev}/fights", json={"fight_number": None, "meron": "A", "wala": "B"})
    check(r.status_code == 400, "fight rejects a null fight_number", f"-> {r.status_code}")


# ========================================================== 7. no 5xx ======
section("7. Every page loads without a server error")
GETS = [r for r in app.url_map.iter_rules()
        if "GET" in r.methods and r.endpoint not in ("static", "logout")]
for creds, label in ((BOSS, "boss"), (ASSISTANT, "assistant")):
    with app.test_client() as c:
        if login(c, creds) is None:
            continue
        bad = []
        for r in GETS:
            url = r.build({k: SAMPLE.get(k, "1") for k in r.arguments})[1]
            code = c.get(url).status_code
            if code >= 500:
                bad.append(f"{url} -> {code}")
        check(not bad, f"{label}: no 5xx on any GET route", "; ".join(bad[:3]))


# --- teardown -------------------------------------------------------------
con.close()
try:
    os.remove(TMP_DB)
except OSError:
    pass

print("\n" + "=" * 72)
if failures:
    print(f"{len(failures)} of {checks} CHECKS FAILED")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print(f"ALL {checks} CHECKS PASSED")
