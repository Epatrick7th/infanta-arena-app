# Infanta Arena — Management System

**[epatrick7th.github.io/infanta-arena-app](https://epatrick7th.github.io/infanta-arena-app/)**

A management system for a cockfighting arena run as an equal partnership.
Six partners share one physical arena and keep their books apart: each
records their own events, fights, revenue and expenses, sees their own profit
and loss, and cannot see anyone else's.

Plain Flask and SQLite. No framework, no build step, no JavaScript bundle.

---

## Running it

```bash
pip install -r requirements.txt
python app.py            # http://localhost:5000
```

First-time setup on an empty database creates the accounts and prints a
random password for each one:

```bash
python setup_bosses.py
python setup_assistants.py
```

To change a password later, use `rotate_password.py`. **Do not** re-run the
setup scripts against a database with data in it: they delete and re-create
the user, which assigns a new id and orphans everything they own. The scripts
now refuse to do this, but the safe path is:

```bash
python rotate_password.py boss_infanta     # one account
python rotate_password.py --all            # everyone
```

The rotation is verified end to end against a scratch copy of the real
database, so the instructions above are known to work rather than merely
written down:

```bash
python tools/check-rotation.py         # --all: every account, logins and data
python tools/check-rotation-paths.py   # the single-account and legacy paths
```

## Tests

```bash
python test_security.py     # 43 checks, runs against a throwaway DB copy
python sanity_check.py      # imports and routes
python tools/check-site.py  # the project site in docs/
```

`test_security.py` is the one that matters. It covers data isolation between
partners, ownership on every write, role scoping, CSRF, and the classes of
bug found during the August 2026 audit. It runs against a copy of the
database, so it never touches real data.

## What is in here

| Path | |
|---|---|
| `app.py` | routes |
| `db.py` | database layer |
| `analytics.py` | profit and loss |
| `live_fight.py` | live fight and betting |
| `boss_approval.py` | approval workflow |
| `templates/` | server-rendered pages |
| `docs/` | the project site ([live](https://epatrick7th.github.io/infanta-arena-app/)) |
| `tools/` | site capture and verification |
| `test_security.py` | security and regression suite |
| `rotate_password.py` | safe in-place password rotation |
| `migrate_live_arena.py` | schema migration for the live-arena feature |

## Before deploying

`BUILD_SUMMARY.md` has the full list. The short version:

1. **Rotate the passwords.** The originals were committed to this public
   repository and must be treated as compromised.
2. Set `SECRET_KEY`, or sessions reset on every restart.
3. Set `COOKIE_SECURE=1` so the session cookie is HTTPS-only.

All figures in the screenshots and sample data are generated, not real arena
finances.
