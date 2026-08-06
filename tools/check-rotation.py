"""Execute the documented rotation procedure literally, and verify the outcome.

My previous check grepped README.md for phrases I had written myself. That
proves nothing: it tests my prose, not the procedure. The question that
matters is whether a person following the documentation ends up with working
logins and intact data.

So: copy the app and database to a scratch directory, run exactly the command
the docs give, then check for every single account that
  - the new password logs in through the real login form
  - the OLD password no longer works
  - the user id is unchanged, so nothing detaches
  - the records they owned before are still theirs afterwards
"""
import os as _os
import sys as _sys

# Runnable from anywhere: anchor to the repository root so `import db` and the
# relative data/ and docs/ paths resolve the same way they do from the root.
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)
_os.chdir(_ROOT)

import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile

SRC = os.path.abspath(".")
work = tempfile.mkdtemp(prefix="rotate_e2e_")
for f in ("rotate_password.py", "db.py", "app.py", "schema.sql", "analytics.py",
          "boss_db.py", "boss_approval.py", "live_fight.py"):
    shutil.copyfile(os.path.join(SRC, f), os.path.join(work, f))
shutil.copytree(os.path.join(SRC, "templates"), os.path.join(work, "templates"))
shutil.copytree(os.path.join(SRC, "static"), os.path.join(work, "static"))
os.makedirs(os.path.join(work, "data"))
db = os.path.join(work, "data", "sabong.db")
shutil.copyfile(os.path.join(SRC, "data", "sabong.db"), db)

fails = []


def check(cond, msg, extra=""):
    print(("  ok   " if cond else "  FAIL ") + msg + (f"  [{extra}]" if extra else ""))
    if not cond:
        fails.append(msg)


def snapshot():
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    users = {r["username"]: r["id"]
             for r in con.execute("select id, username from users")}
    owned = {}
    for uid in users.values():
        owned[uid] = tuple(
            con.execute(f"select count(*) from {t} where boss_id=?",
                        (uid,)).fetchone()[0]
            for t in ("events", "expenses", "cash_remittances", "fights"))
    con.close()
    return users, owned


# the passwords the repo says were exposed
OLD = {"boss_infanta": "infanta123", "boss_royal": "royal123",
       "boss_champion": "champion123", "boss_phoenix": "phoenix123",
       "boss_golden": "golden123", "boss_elite": "elite123",
       "asst_infanta": "infanta_asst", "asst_royal": "royal_asst",
       "patrick": "password123", "test_boss": "test123"}

before_users, before_owned = snapshot()
print(f"before: {len(before_users)} users\n")

# --- run EXACTLY what the documentation tells the owner to run ---
print("running: python rotate_password.py --all")
r = subprocess.run([sys.executable, "rotate_password.py", "--all"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=work)
check(r.returncode == 0, "the documented command succeeds", f"rc={r.returncode}")
if r.returncode:
    print(r.stdout[-800:], r.stderr[-800:])

issued = dict(re.findall(r"^\s{2}(\S+)\s+\S+\s+(\S+)$", r.stdout, re.M))
check(len(issued) == len(before_users),
      f"a password was issued for all {len(before_users)} accounts",
      f"got {len(issued)}")

after_users, after_owned = snapshot()

# --- ids must not move, or data detaches ---
moved = [u for u in before_users if before_users[u] != after_users.get(u)]
check(not moved, "every user id is unchanged", str(moved))

# --- and their records must still be theirs ---
changed = [uid for uid in before_owned if before_owned[uid] != after_owned.get(uid)]
check(not changed, "record ownership counts are identical", str(changed))

# --- the real proof: log in through the app with the new passwords ---
sys.path.insert(0, work)
os.chdir(work)
import db as D
D.DB_PATH = db
import app as A
A.app.config["TESTING"] = True

new_ok, old_dead = 0, 0
for user, pwd in issued.items():
    with A.app.test_client() as c:
        c.post("/login", data={"username": user, "password": pwd})
        with c.session_transaction() as s:
            if s.get("user_id") == after_users[user]:
                new_ok += 1
            else:
                print(f"       new password failed for {user}")
    if user in OLD:
        with A.app.test_client() as c:
            c.post("/login", data={"username": user, "password": OLD[user]})
            with c.session_transaction() as s:
                if s.get("user_id") is None:
                    old_dead += 1
                else:
                    print(f"       OLD password STILL WORKS for {user}")

check(new_ok == len(issued),
      f"all {len(issued)} accounts log in with their new password", f"{new_ok} ok")
tested_old = [u for u in issued if u in OLD]
check(old_dead == len(tested_old),
      f"all {len(tested_old)} known-exposed passwords are dead", f"{old_dead} dead")

# --- a rotated partner still sees their own books, and only theirs ---
boss = "boss_infanta"
with A.app.test_client() as c:
    c.post("/login", data={"username": boss, "password": issued[boss]})
    html = c.get("/events").get_data(as_text=True)
    cards = len(re.findall(r'href="/events/\d+"', html))
    con = sqlite3.connect(db)
    owns = con.execute("select count(*) from events where boss_id=? and deleted_at is null",
                       (after_users[boss],)).fetchone()[0]
    con.close()
    check(cards == owns and cards > 0,
          f"{boss} still sees their {owns} events after rotation", f"{cards} cards")

os.chdir(SRC)
shutil.rmtree(work, ignore_errors=True)
print("\nscratch copy removed; the real database was never touched")
print("\n" + ("DOCUMENTED PROCEDURE WORKS END TO END"
              if not fails else f"{len(fails)} FAILURES: {fails}"))
sys.exit(1 if fails else 0)
