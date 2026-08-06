"""Security and regression suite for the Infanta Arena app.

Run:  python test_security.py

Covers the defects found on 2026-08-05, so they cannot come back:

  1. anonymous access      every non-public route redirects to /login
  2. list isolation        a boss sees only their own events/expenses/remittances
  3. IDOR                  a boss cannot read or mutate another boss's records
  4. write ownership       new rows are stamped with the creating boss
  5. assistant scoping     an assistant resolves to their arena's boss
  6. JSON coercion         the write APIs accept JSON numbers and strings
  7. CSRF                  cross-site writes are refused, same-site are not
  8. coverage audit        no unowned insert or unfiltered read remains
  9. no 5xx                every GET page loads for boss and assistant

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

# Credentials come from the environment, with the throwaway development
# values as fallbacks so the suite runs out of the box on a local database.
# These are not secrets: setup_bosses.py now issues a random password per
# account, so a real deployment never has a known one. Point the suite at a
# different database with:
#   set ARENA_TEST_BOSS_PASSWORD=...
DEV_FALLBACK = {
    "boss": "infanta123",
    "boss2": "royal123",
    "assistant": "infanta_asst",
}
BOSS = (os.environ.get("ARENA_TEST_BOSS_USER", "boss_infanta"),
        os.environ.get("ARENA_TEST_BOSS_PASSWORD", DEV_FALLBACK["boss"]))
BOSS2 = (os.environ.get("ARENA_TEST_BOSS2_USER", "boss_royal"),
         os.environ.get("ARENA_TEST_BOSS2_PASSWORD", DEV_FALLBACK["boss2"]))
ASSISTANT = (os.environ.get("ARENA_TEST_ASSISTANT_USER", "asst_infanta"),
             os.environ.get("ARENA_TEST_ASSISTANT_PASSWORD",
                            DEV_FALLBACK["assistant"]))

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


# ============================================================ 7. CSRF ======
section("7. Cross-site writes are rejected, same-site writes are not")
with app.test_client() as c:
    login(c, BOSS)
    form = {"date": date.today().isoformat(), "amount": "10",
            "description": "csrf case", "category": "supplies"}

    def expense_count():
        return con.execute("select count(*) from expenses").fetchone()[0]

    before = expense_count()
    c.post("/expenses/new", data=dict(form, description="same-origin"),
           headers={"Origin": "http://localhost",
                    "Referer": "http://localhost/expenses/new"},
           base_url="http://localhost")
    check(expense_count() == before + 1, "same-origin browser POST is accepted")

    before = expense_count()
    c.post("/expenses/new", data=dict(form, description="no-origin"))
    check(expense_count() == before + 1, "client with no Origin/Referer is accepted")

    before = expense_count()
    r = c.post("/expenses/new", data=dict(form, description="forged"),
               headers={"Origin": "https://evil.example"})
    check(r.status_code == 403 and expense_count() == before,
          "cross-site form POST is rejected", f"-> {r.status_code}")

    ev = con.execute("select id from events limit 1").fetchone()["id"]
    r = c.post(f"/api/events/{ev}/revenue", json={"source": "gate", "amount": 1},
               headers={"Origin": "https://evil.example"})
    check(r.status_code == 403, "cross-site JSON POST is rejected", f"-> {r.status_code}")

    r = c.get("/dashboard", headers={"Origin": "https://evil.example"})
    check(r.status_code == 200, "GET is unaffected by the origin check",
          f"-> {r.status_code}")

    check(app.config.get("SESSION_COOKIE_SAMESITE") == "Lax",
          "session cookie is SameSite=Lax",
          str(app.config.get("SESSION_COOKIE_SAMESITE")))


# ================================================== 8. coverage audit ======
section("8. No unowned inserts or unfiltered reads remain")
import inspect
import re as _re

owned_tables = set()
for (_t,) in con.execute(
        "select name from sqlite_master where type='table' and name not like 'sqlite_%'"):
    if "boss_id" in {r[1] for r in con.execute(f"PRAGMA table_info({_t})")}:
        owned_tables.add(_t)

# users.boss_id links an assistant to a boss; it is not row ownership
BY_DESIGN = {"users"}
db_src = open("db.py", encoding="utf-8").read()

insert_gaps = []
for m in _re.finditer(r'"INSERT INTO (\w+) \(([^)]*)\)', db_src):
    table, cols = m.group(1), m.group(2)
    if table in owned_tables and table not in BY_DESIGN and "boss_id" not in cols:
        insert_gaps.append(table)
check(not insert_gaps, "every insert into a boss-owned table records boss_id",
      str(insert_gaps))

# reads excused below are by-id or parent-scoped; section 3 proves their
# routes refuse cross-boss access
BY_ID_OK = {"get_event", "get_fight", "get_event_summary",
            "list_fights_for_event", "list_event_revenue"}
USERS_OK = {"verify_user", "list_users", "get_user", "delete_user",
            "update_user_role", "create_user"}
read_gaps = []
for name in dir(D):
    if not (name.startswith("list_") or name.startswith("get_")) or name == "get_connection":
        continue
    fn = getattr(D, name)
    if not callable(fn):
        continue
    try:
        body = inspect.getsource(fn)
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError, OSError):
        continue
    hit = {t for t in owned_tables if _re.search(rf"\bFROM {t}\b", body)}
    if not hit or name in BY_ID_OK or name in USERS_OK or hit == {"users"}:
        continue
    if "boss_id" not in params:
        read_gaps.append(name)
check(not read_gaps, "every book-level read can filter by boss", str(read_gaps))

# No committed credentials: this repo is public, so anything written into a
# tracked file is world-readable. Two live passwords (a boss and the
# super_admin) were found this way.
#
# The suite's own DEV_FALLBACK block is the single allowed exception: those
# are the throwaway values on a local dev database, and setup_bosses.py now
# issues random passwords so production never has a known one. The exception
# is spelled out here rather than by exempting a whole file, because an
# exempt file is exactly where the next secret would land.
import glob as _glob

CRED_PATTERN = _re.compile(
    r"""['"]password['"]\s*:\s*['"][^'"]{3,}['"]"""      # {'password': 'secret'}
    r"""|_pwd['"]?\s*[:=]\s*['"][^'"]{3,}['"]"""         # asst_pwd = 'secret'
    r"""|password\s*=\s*['"][^'"]{3,}['"]""",            # password = 'secret'
    _re.IGNORECASE)

ALLOWED_LINES = _re.compile(
    r'DEV_FALLBACK|os\.environ|getenv|request\.form|\.get\('
    r'|CRED_PATTERN|_re\.compile|# .*secret')  # the guard's own definition

cred_hits = []
for pyfile in _glob.glob("*.py"):
    # scratch probes are gitignored and never published; no tracked file is
    # exempt, including this one
    if pyfile.startswith("_"):
        continue
    in_pattern = False
    for lineno, line in enumerate(
            open(pyfile, encoding="utf-8", errors="replace"), 1):
        # skip the regex literal that defines this very check
        if "CRED_PATTERN = " in line:
            in_pattern = True
        if in_pattern:
            if line.rstrip().endswith(")"):
                in_pattern = False
            continue
        if ALLOWED_LINES.search(line):
            continue
        if CRED_PATTERN.search(line):
            cred_hits.append(f"{pyfile}:{lineno}")
check(not cred_hits, "no hardcoded password literals in committed scripts",
      "; ".join(cred_hits[:4]))

# The check above only sees the working tree. Git keeps everything, and this
# repository is public, so a secret committed once is readable forever even
# after it is deleted. Two things matter most:
#   - the database itself must never have been committed (that would publish
#     the partners' actual financials, far worse than the passwords)
#   - no API key, token or private key anywhere in history
import subprocess as _sp


def _git(*args):
    return _sp.run(["git", *args], capture_output=True, text=True,
                   encoding="utf-8", errors="replace").stdout


_hist_paths = {p for p in _git("log", "--pretty=format:", "--name-only",
                               "--all").split("\n") if p.strip()}
_db_committed = sorted(p for p in _hist_paths
                       if p.lower().endswith((".db", ".sqlite", ".sqlite3")))
check(not _db_committed, "the database was never committed to history",
      str(_db_committed))

_SECRET_PATTERNS = [
    (r"gh[pousr]_[A-Za-z0-9]{16,}", "GitHub token"),
    (r"AKIA[0-9A-Z]{16}", "AWS key"),
    (r"AIza[0-9A-Za-z_\-]{35}", "Google API key"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "private key"),
]
_secret_hits = []
for _pat, _label in _SECRET_PATTERNS:
    if _git("log", "--all", "--oneline", "-S", _pat, "--pickaxe-regex").strip():
        _secret_hits.append(_label)
check(not _secret_hits, "no API keys or private keys in git history",
      str(_secret_hits))


# ============================================== 9. list pages render ======
section("9. List pages show the owner's records, and only theirs")
with app.test_client() as c:
    uid = login(c, BOSS)
    import re as _re2

    html = c.get("/events").get_data(as_text=True)
    owned = con.execute(
        "select count(*) n from events where boss_id=? and deleted_at is null",
        (uid,)).fetchone()["n"]
    cards = len(_re2.findall(r'href="/events/\d+"', html))
    check("No events yet" not in html and cards > 0,
          f"events page lists the owner's {owned} events", f"{cards} cards")

    other = con.execute(
        "select id from events where boss_id<>? limit 1", (uid,)).fetchone()
    if other:
        check(f'href="/events/{other["id"]}"' not in html,
              "another partner's event is not listed on the page")

    html = c.get("/expenses").get_data(as_text=True)
    check("No expenses recorded yet" not in html, "expenses page lists rows")

    html = c.get("/remittances").get_data(as_text=True)
    check("No remittances yet" not in html, "remittances page lists rows")

# The /events bug was a template gated on a variable the route never passed:
# it rendered blank, silently, with no error. Jinja's default is to treat an
# undefined name as empty, which is exactly what hid it. Re-render every page
# with StrictUndefined so that class of bug raises instead of rendering an
# empty screen.
from jinja2 import StrictUndefined as _Strict

_prev_undefined = app.jinja_env.undefined
app.jinja_env.undefined = _Strict
undef_fails = []
try:
    with app.test_client() as c:
        login(c, BOSS)
        for r in app.url_map.iter_rules():
            if "GET" not in r.methods or r.endpoint in ("static", "logout"):
                continue
            url = r.build({k: SAMPLE.get(k, "1") for k in r.arguments})[1]
            try:
                if c.get(url).status_code >= 500:
                    undef_fails.append(url)
            except Exception as e:
                undef_fails.append(f"{url} ({type(e).__name__})")
finally:
    app.jinja_env.undefined = _prev_undefined
check(not undef_fails, "no page uses a template variable its route never passes",
      "; ".join(undef_fails[:3]))


# ========================================================== 10. no 5xx =====
section("10. Every page loads without a server error")
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
