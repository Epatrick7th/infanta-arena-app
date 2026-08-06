"""Would the site checks have caught the flaws in the EARLY site work?

The review's point: check-site.py was written partway through, so the first
version of the site never passed through it. Passing now is weak evidence,
because the early flaws were already fixed by the time the loop existed.

The real question is whether the loop I ended up with is capable of catching
them. So reconstruct each early flaw in a scratch copy of docs/ and see what
the checker actually reports.

Early flaws, from the record:
  1. an unreferenced screenshot shipped (3 captured but unused)
  2. the page's figures drifting from the repo (claimed 35, suite had 39)
  3. a referenced screenshot missing from disk
  4. a broken internal anchor
Two others were visual (mismatched card heights, a caption contradicting its
screenshot) and are honestly outside what any of these checks can see; that
is stated rather than papered over.
"""
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile

SRC = os.path.abspath(".")
results = []


def run_checker(workdir):
    """Run check-site.py against a scratch copy and return (rc, failures)."""
    r = subprocess.run([sys.executable, "tools/check-site.py"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=workdir)
    fails = [l.strip() for l in (r.stdout or "").splitlines() if "FAIL" in l]
    return r.returncode, fails


def scratch():
    work = tempfile.mkdtemp(prefix="site_regress_")
    shutil.copytree(os.path.join(SRC, "docs"), os.path.join(work, "docs"))
    os.makedirs(os.path.join(work, "tools"))
    shutil.copyfile(os.path.join(SRC, "tools", "check-site.py"),
                    os.path.join(work, "tools", "check-site.py"))
    for f in ("app.py", "test_security.py", "db.py", "schema.sql", "analytics.py",
              "boss_db.py", "boss_approval.py", "live_fight.py"):
        shutil.copyfile(os.path.join(SRC, f), os.path.join(work, f))
    shutil.copytree(os.path.join(SRC, "templates"), os.path.join(work, "templates"))
    os.makedirs(os.path.join(work, "data"))
    shutil.copyfile(os.path.join(SRC, "data", "sabong.db"),
                    os.path.join(work, "data", "sabong.db"))
    return work


def edit(work, fn):
    p = os.path.join(work, "docs", "index.html")
    s = io.open(p, encoding="utf-8", newline="").read()
    io.open(p, "w", encoding="utf-8", newline="").write(fn(s))


# --- baseline: the current site must pass in the scratch copy ---
w = scratch()
rc, fails = run_checker(w)
print(f"baseline (current site): rc={rc} fails={fails or 'none'}")
results.append(("baseline passes", rc == 0))
shutil.rmtree(w, ignore_errors=True)

# --- flaw 1: an unreferenced screenshot shipped ---
w = scratch()
shutil.copyfile(os.path.join(w, "docs", "screenshots", "login.webp"),
                os.path.join(w, "docs", "screenshots", "orphan.webp"))
rc, fails = run_checker(w)
caught = rc != 0 and any("unreferenced" in f for f in fails)
print(f"\nflaw 1 unreferenced screenshot: {'CAUGHT' if caught else 'MISSED'}")
for f in fails:
    print("   ", f)
results.append(("catches an unreferenced screenshot", caught))
shutil.rmtree(w, ignore_errors=True)

# --- flaw 2: figures drift from the repo ---
w = scratch()
edit(w, lambda s: re.sub(r"<b>\d+</b><span>Security checks</span>",
                         "<b>35</b><span>Security checks</span>", s))
rc, fails = run_checker(w)
caught = rc != 0 and any("count matches" in f for f in fails)
print(f"\nflaw 2 stale figures (claims 35): {'CAUGHT' if caught else 'MISSED'}")
for f in fails:
    print("   ", f)
results.append(("catches figures drifting from the repo", caught))
shutil.rmtree(w, ignore_errors=True)

# --- flaw 3: a referenced screenshot missing from disk ---
w = scratch()
os.remove(os.path.join(w, "docs", "screenshots", "events.webp"))
rc, fails = run_checker(w)
caught = rc != 0 and any("exist" in f or "render" in f for f in fails)
print(f"\nflaw 3 missing screenshot: {'CAUGHT' if caught else 'MISSED'}")
for f in fails:
    print("   ", f)
results.append(("catches a missing screenshot", caught))
shutil.rmtree(w, ignore_errors=True)

# --- flaw 4: a broken internal anchor ---
w = scratch()
edit(w, lambda s: s.replace('href="#security"', 'href="#nonexistent"', 1))
rc, fails = run_checker(w)
caught = rc != 0 and any("anchor" in f for f in fails)
print(f"\nflaw 4 broken anchor: {'CAUGHT' if caught else 'MISSED'}")
for f in fails:
    print("   ", f)
results.append(("catches a broken internal anchor", caught))
shutil.rmtree(w, ignore_errors=True)

print("\n" + "=" * 66)
bad = [n for n, ok in results if not ok]
for name, ok in results:
    print(("  ok   " if ok else "  FAIL ") + name)

# --- the fifth early flaw is now covered at capture time, not by the checker ---
cap = io.open(os.path.join(SRC, "tools", "capture-screenshots.py"),
              encoding="utf-8").read()
guard = ("No Fights Scheduled" in cap and "NOT SAVED" in cap
         and "EMPTY_STATES" in cap)
print(("  ok   " if guard else "  FAIL ")
      + "a screenshot showing an empty state is refused at capture time")
results.append(("capture guard present", guard))
if not guard:
    bad.append("capture guard")

print("\nSTILL NOT COVERED by any automated check (visual review only):")
print("  - mismatched card heights / stretched images")
print("    aesthetic, does not mislead; a machine cannot judge it")

sys.exit(1 if bad else 0)
