# TONSCOPE

Desktop username research tool built with Python and PySide6.

## Version 0.2

- Generates lowercase Latin usernames of 5, 6 and 7 letters.
- Readable, word-like, brandable and random modes, including mixed 5-7 scanning.
- 1-10 readability, pronounceability, uniqueness, brandability and liquidity heuristics.
- Live public Telegram presence and Fragment collectible checks through a bulk resolver.
- Up to 15 usernames per request, configurable request pacing.
- Separate AVAILABLE, OCCUPIED, FRAGMENT AUCTION, FRAGMENT COLLECTIBLE and CHECK ERROR states.
- SQLite persistence, interrupted-candidate recovery, STOP, rechecking saved/selected usernames, and multiple local profiles.
- New, Saved and Checked views; CSV, JSON and TXT export.
- Fragment's observed TON ask and cached TON/USD + USD/RUB conversion.
- Comparable range appears only after at least three observed active Fragment asks of the same username length. This is a current-ask reference range, not a guaranteed resale value.

## Install and run on Windows

Run `start.bat`. It creates a virtual environment, installs PySide6 and starts the app.

Manual run:

```powershell
py -3.12 -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
python main.py
```

## User data

Settings and profiles are stored outside Git: `%APPDATA%/TONSCOPE/` on Windows and `~/.config/TONSCOPE/` on Linux (or `$XDG_CONFIG_HOME/TONSCOPE/`). The default database is `profiles/default/tonscope.db`.

## Public checker

Default endpoint: `https://tg-username-api.vercel.app/api/v1`. It checks public Telegram pages and Fragment listing pages and requires no Telegram login. Its documentation states a maximum of 25 API requests/minute and up to 15 usernames per bulk request. TONSCOPE defaults to 20 bulk requests/minute.

This is a third-party public-data resolver, not an official Telegram or Fragment API. Ambiguous and failed checks are stored as CHECK ERROR, never AVAILABLE. Fragment prices are only displayed when the resolver returns an observed public price; no price is fabricated for an unlisted username.

## Tests

```powershell
python -m compileall -q main.py tonscope tests
python -m unittest discover -s tests -v
```
