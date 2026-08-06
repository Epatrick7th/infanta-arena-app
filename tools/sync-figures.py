"""Update the figures on the project site and the README to match the repo.

The site's drift check caught the page claiming 35 security checks while the
suite had 39; the README check then caught the same thing at 40 vs 42.
Reading the real numbers rather than hardcoding them keeps both honest.
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
    print("suite did not pass; refusing to update the docs")
    sys.exit(1)
checks = m.group(1)


def rewrite(path, subs):
    raw = io.open(path, encoding="utf-8", newline="").read()
    crlf = "\r\n" in raw
    flat = raw.replace("\r\n", "\n")
    before = flat
    for pat, repl in subs:
        flat = re.sub(pat, repl, flat)
    io.open(path, "w", encoding="utf-8", newline="").write(
        flat.replace("\n", "\r\n") if crlf else flat)
    return flat != before


site = rewrite("docs/index.html", [
    (r"<b>\d+</b><span>Routes</span>", f"<b>{routes}</b><span>Routes</span>"),
    (r"<b>\d+</b><span>Security checks</span>",
     f"<b>{checks}</b><span>Security checks</span>"),
    (r"\d+ checks passing", f"{checks} checks passing"),
])

readme = rewrite("README.md", [
    (r"\d+ checks, runs against", f"{checks} checks, runs against"),
])

print(f"routes={routes}  checks={checks}")
print(f"  docs/index.html: {'updated' if site else 'already correct'}")
print(f"  README.md:       {'updated' if readme else 'already correct'}")
