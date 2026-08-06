"""Verify the remaining documented rotation paths, not just --all.

The docs offer three ways in, and a reader may take any of them:
  1. python rotate_password.py <user>              single account
  2. python rotate_password.py <user> --password X chosen password
  3. python fix_user.py                            old script, now delegating
plus the warning that re-running setup_bosses.py would orphan data.

Each is tested on its own scratch copy.
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
fails = []


def check(cond, msg, extra=""):
    print(("  ok   " if cond else "  FAIL ") + msg + (f"  [{extra}]" if extra else ""))
    if not cond:
        fails.append(msg)


def scratch():
    work = tempfile.mkdtemp(prefix="rot_paths_")
    for f in ("rotate_password.py", "fix_user.py", "setup_bosses.py",
              "setup_assistants.py", "db.py", "schema.sql"):
        shutil.copyfile(os.path.join(SRC, f), os.path.join(work, f))
    os.makedirs(os.path.join(work, "data"))
    shutil.copyfile(os.path.join(SRC, "data", "sabong.db"),
                    os.path.join(work, "data", "sabong.db"))
    return work, os.path.join(work, "data", "sabong.db")


def run(work, *args, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    return subprocess.run([sys.executable, *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", cwd=work, env=e)


def verify(db, user, pwd, old_pwd, expect_id):
    from werkzeug.security import check_password_hash
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    row = con.execute("select id, password_hash from users where username=?",
                      (user,)).fetchone()
    ev = con.execute("select count(*) from events where boss_id=?",
                     (row["id"],)).fetchone()[0]
    con.close()
    return (row["id"] == expect_id,
            check_password_hash(row["password_hash"], pwd),
            not check_password_hash(row["password_hash"], old_pwd),
            ev)


USER = "boss_infanta"
OLD = "infanta123"

# --- path 1: single account, generated password ---
print("path 1: rotate_password.py <user>")
work, db = scratch()
before = sqlite3.connect(db).execute(
    "select id from users where username=?", (USER,)).fetchone()[0]
before_ev = sqlite3.connect(db).execute(
    "select count(*) from events where boss_id=?", (before,)).fetchone()[0]
r = run(work, "rotate_password.py", USER)
m = re.search(rf"{USER}\s+\S+\s+(\S+)", r.stdout)
pwd = m.group(1) if m else None
check(r.returncode == 0 and pwd, "single-account rotation runs", f"rc={r.returncode}")
if pwd:
    same_id, new_ok, old_dead, ev = verify(db, USER, pwd, OLD, before)
    check(same_id, "id unchanged")
    check(new_ok, "new password works")
    check(old_dead, "old password dead")
    check(ev == before_ev, f"still owns {before_ev} events", f"{ev}")
shutil.rmtree(work, ignore_errors=True)

# --- path 2: chosen password ---
print("\npath 2: rotate_password.py <user> --password ...")
work, db = scratch()
CHOSEN = "a-long-chosen-passphrase-2026"
r = run(work, "rotate_password.py", USER, "--password", CHOSEN)
check(r.returncode == 0, "chosen-password rotation runs", f"rc={r.returncode}")
same_id, new_ok, old_dead, ev = verify(db, USER, CHOSEN, OLD, before)
check(new_ok, "the chosen password works")
check(old_dead, "old password dead")
check(same_id, "id unchanged")
shutil.rmtree(work, ignore_errors=True)

# --- path 3: the deprecated script still in shell history ---
print("\npath 3: fix_user.py (deprecated, delegates)")
work, db = scratch()
r = run(work, "fix_user.py", env={"FIX_USER": USER, "NEW_PASSWORD": CHOSEN})
check(r.returncode == 0, "fix_user.py runs", f"rc={r.returncode}")
check("rotate_password.py" in r.stdout, "it points at the safe tool")
same_id, new_ok, old_dead, ev = verify(db, USER, CHOSEN, OLD, before)
check(same_id and new_ok, "it rotated safely without moving the id")
check(ev == before_ev, "data still attached", f"{ev}")
shutil.rmtree(work, ignore_errors=True)

# --- the documented warning: setup scripts must refuse ---
print("\nthe documented warning: setup scripts refuse on a populated database")
work, db = scratch()
r = run(work, "setup_bosses.py")
after_id = sqlite3.connect(db).execute(
    "select id from users where username=?", (USER,)).fetchone()[0]
check(r.returncode != 0, "setup_bosses.py refuses", f"rc={r.returncode}")
check(after_id == before, "no id was reassigned", f"{before} -> {after_id}")
shutil.rmtree(work, ignore_errors=True)

print("\n" + ("ALL DOCUMENTED PATHS WORK" if not fails else f"{len(fails)} FAILURES: {fails}"))
sys.exit(1 if fails else 0)
