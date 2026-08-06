"""Update the figures on the page to match the repo.

The site's drift check caught this: the page claimed 35 security checks
while the suite now has 39, after the list-page checks were added. Reading
the real numbers rather than hardcoding them keeps the page honest.
"""
import io
import re
import subprocess
import sys

app_src = io.open("app.py", encoding="utf-8").read()
routes = len(re.findall(r"@app\.route", app_src))

r = subprocess.run([sys.executable, "test_security.py"], capture_output=True,
                   text=True, encoding="utf-8", errors="replace")
m = re.search(r"ALL (\d+) CHECKS PASSED", r.stdout or "")
if not m:
    print("suite did not pass; refusing to update the page")
    sys.exit(1)
checks = m.group(1)

path = "docs/index.html"
raw = io.open(path, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
flat = raw.replace("\r\n", "\n")

before = flat
flat = re.sub(r"<b>\d+</b><span>Routes</span>",
              f"<b>{routes}</b><span>Routes</span>", flat)
flat = re.sub(r"<b>\d+</b><span>Security checks</span>",
              f"<b>{checks}</b><span>Security checks</span>", flat)
flat = re.sub(r"\d+ checks passing", f"{checks} checks passing", flat)

io.open(path, "w", encoding="utf-8", newline="").write(
    flat.replace("\n", "\r\n") if crlf else flat)

print(f"routes={routes}  checks={checks}  "
      f"{'updated' if flat != before else 'already correct'}")
