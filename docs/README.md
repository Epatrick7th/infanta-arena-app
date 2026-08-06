# Project site (`docs/`)

The GitHub Pages showcase for this app: <https://epatrick7th.github.io/infanta-arena-app/>

It is a single static page. There is no build step, no framework and no
external JavaScript; only the Google Fonts stylesheet is remote.

## Status

Pages is **enabled** and the site is live at the URL above, serving from
`main` / `/docs` over HTTPS. Every push to `main` republishes it within about
a minute.

To verify the published site rather than the local files:

```bash
python tools/check-live-site.py
```

It fetches the real URL, renders it at desktop and phone width, and checks
every screenshot decodes over HTTPS.

## Why a static showcase and not a demo

The app is Flask plus SQLite, so GitHub Pages cannot run it: Pages serves
static files only. A public live demo would also mean publishing a login
page and a database on the open internet, which is the wrong trade for an
app whose whole purpose is keeping six partners' finances separate.

So the page shows the software rather than hosting it. Every screenshot is
captured from the app actually running against the generated sample month,
never mocked up, so the page cannot show something the code does not do.

## Regenerating it

```bash
python tools/capture-screenshots.py     # capture from the running app
python tools/capture-live-arena.py      # live fight with bets on both sides
python tools/optimise-screenshots.py    # 2x PNG -> half-size WebP (~98% smaller)
python tools/check-site.py              # verify before pushing
```

`check-site.py` is the one that matters. It asserts:

- every screenshot the page references exists and actually decodes
- no horizontal overflow at 390, 768 and 1440 px
- no JavaScript errors, and every local asset loads
- internal anchors resolve
- **the numbers on the page match the repository** — the route count is read
  from `app.py` and the check count from `test_security.py`, so the page
  cannot quietly drift out of date after a change

## Notes

- All figures shown are generated sample data, not real arena finances.
- `capture-live-arena.py` seeds an uneven bet split on purpose. An earlier
  run produced exactly 50/50, which reads as fabricated.
- Screenshots are captured at 2x then halved, which keeps them sharp on
  retina displays while taking the payload from 13.2 MB to about 0.3 MB.
