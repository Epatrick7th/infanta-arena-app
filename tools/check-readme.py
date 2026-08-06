"""Verify the README's claims rather than trusting them.

A README that says "40 checks" or lists files that do not exist is the same
class of problem as the docs that claimed CSRF protection existed.
"""
import os as _os
import sys as _sys

# Runnable from anywhere: anchor to the repository root so `import db` and the
# relative data/ and docs/ paths resolve the same way they do from the root.
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)
_os.chdir(_ROOT)

import io
import pathlib
import re
import subprocess
import sys
import urllib.request

readme = io.open("README.md", encoding="utf-8").read()
fails = []


def check(cond, msg, extra=""):
    print(("  ok   " if cond else "  FAIL ") + msg + (f"  [{extra}]" if extra else ""))
    if not cond:
        fails.append(msg)


# every file the table mentions must exist
paths = re.findall(r"\| `([\w./]+)` \|", readme)
missing = [p for p in paths if not pathlib.Path(p.rstrip("/")).exists()]
check(not missing, f"all {len(paths)} referenced paths exist", str(missing))

# the check count must match the suite
r = subprocess.run([sys.executable, "test_security.py"], capture_output=True,
                   text=True, encoding="utf-8", errors="replace")
m = re.search(r"ALL (\d+) CHECKS PASSED", r.stdout or "")
actual = m.group(1) if m else "?"
claimed = re.search(r"(\d+) checks", readme)
check(claimed and claimed.group(1) == actual,
      "check count matches the suite",
      f"README={claimed.group(1) if claimed else '?'} actual={actual}")

# every command must be runnable (module exists / file present)
cmds = re.findall(r"python ([\w./\\-]+\.py)", readme)
bad = [c for c in set(cmds) if not pathlib.Path(c.replace("/", "\\")).exists()
       and not pathlib.Path(c).exists()]
check(not bad, f"all {len(set(cmds))} referenced scripts exist", str(bad))

# the live link must resolve
url = re.search(r"\((https://[\w./-]+)\)", readme).group(1)
try:
    req = urllib.request.Request(url, headers={"User-Agent": "check"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        check(resp.status == 200, f"live link resolves ({url})", str(resp.status))
except Exception as e:
    check(False, f"live link resolves ({url})", str(e))

# the rotation claim: setup scripts really do refuse on a populated DB
r2 = subprocess.run([sys.executable, "setup_bosses.py"], capture_output=True,
                    text=True, encoding="utf-8", errors="replace")
check(r2.returncode != 0 and "REFUSING" in r2.stdout,
      "setup scripts refuse to run against the populated database",
      f"rc={r2.returncode}")

print("\n" + ("README CLAIMS VERIFIED" if not fails else f"{len(fails)} FAILURES: {fails}"))
sys.exit(1 if fails else 0)
