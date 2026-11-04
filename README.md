# TONSCOPE

Desktop username research tool built with Python and PySide6.

## Version 0.2

- Generates 5, 6 and 7 character lowercase Latin usernames.
- Readable, word-like, brandable and random generation modes.
- Mixed-length scanning and minimum quality score.
- Live public Telegram presence and Fragment collectible checks through a bulk resolver.
- Up to 15 names per API request; configurable request pacing.
- Separate AVAILABLE, OCCUPIED, FRAGMENT AUCTION, FRAGMENT COLLECTIBLE and CHECK ERROR states.
- Automatic SQLite persistence, profile data outside the repository, resumable interrupted candidates.
- STOP, recheck saved/selected usernames, new/saved/checked views.
- CSV, JSON and TXT export.
- Fragment's observed TON ask, TON/USD and USD/RUB conversion.
- Comparable range from at least three observed active Fragment asks of the same username length. This is a current-ask reference range, not a guaranteed resale value.

## Install

\`\`\`powershell
py -3.12 -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
python main.py
\`\`\`

## User data

Settings and profiles are stored outside Git:
- Windows: %APPDATA%/TONSCOPE/
- Linux: ~/.config/TONSCOPE/ or $XDG_CONFIG_HOME/TONSCOPE/

The default database is profiles/default/tonscope.db.

## Public checker

Default endpoint: https://tg-username-api.vercel.app/api/v1

The resolver checks public Telegram pages and Fragment listing pages. It requires no Telegram login. Its documentation states a maximum of 25 API requests per minute and up to 15 usernames per bulk request. TONSCOPE defaults to 20 bulk requests per minute.

This is a third-party public-data resolver, not an official Telegram or Fragment API. Ambiguous and failed checks are stored as CHECK ERROR, never as AVAILABLE. Fragment prices are only displayed when the resolver returns an observed public price; TONSCOPE does not invent a price for an unlisted username.

## Tests

\`\`\`powershell
python -m compileall -q main.py tonscope tests
python -m unittest discover -s tests -v
\`\`\`
