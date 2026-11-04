# TONSCOPE

Desktop username research tool built with Python and PySide6.

## Current stage

- Minimal dark desktop interface.
- Local SQLite profile database.
- Username candidate generation (5, 6 or 7 lowercase Latin letters).
- Readability and brandability scoring.
- Persistent candidate history and saved list.
- Search worker runs outside the UI thread and supports Stop.
- No candidate is marked as available until a real Telegram check confirms it.

Telegram and Fragment adapters are deliberately isolated and will be integrated in the next stage. Price estimates must be based on actual comparable market data and exchange rates, not fabricated values.

## Run

```bash
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

On Linux/macOS, activate the virtual environment using its platform-specific command.

User data is stored locally in `user_data/profiles/default/tonscope.db`.

## Project layout

- `tonscope/core`: generation, scoring and scan worker.
- `tonscope/storage`: SQLite persistence.
- `tonscope/ui`: PySide6 interface.
- `user_data`: local profiles (not committed to Git).
