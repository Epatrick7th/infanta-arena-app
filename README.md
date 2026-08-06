# Infanta Arena — Management System

**Public site:** [epatrick7th.github.io/infanta-arena-app](https://epatrick7th.github.io/infanta-arena-app/)
— the arena's client-facing landing page.
**Technical write-up:** [/system/](https://epatrick7th.github.io/infanta-arena-app/system/)
— how the system works and what the audit found.

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

## Who can change what

Each arena has two logins, and they are deliberately not equivalent.

| Role | Can see | Can change |
| --- | --- | --- |
| **Boss** (the partner) | their whole arena: events, expenses, remittances, personnel, analytics | nothing |
| **Assistant** | the same arena | records data and approves or rejects pending items |

The boss is strictly read-only. This is enforced in one place, a
`before_request` hook that refuses every mutating request from a boss, rather
than route by route where one missed decorator would reopen the hole. The
action buttons are also hidden from the boss, so nobody is offered a control
that would only fail.

The point is that a figure a partner disputes always has an author who is not
that partner. Every record stores who created it and when, and the same for
who approved it, and the boss can see both.

A boss cannot see any other partner's books, whatever their own role.

## The public site

`docs/` is published by GitHub Pages. The landing page is not written by
hand: it is rendered from `templates/landing4.html` through the real app, so
the published page cannot drift from the one running locally.

```bash
python tools/build-pages.py   # render /v4 into docs/
python tools/check-pages.py   # serve docs/ and drive it in a browser
```

**The fight schedule is baked in at build time.** The build prints the date
range it froze. Rerun it when those dates pass, or the site will advertise
fights that are over.

## Tests



```bash
python test_security.py     # 49 checks, runs against a throwaway DB copy
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
