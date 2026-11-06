# AGENTS.md

## Project
Nova Campus Tycoon, a day-based café management game in Streamlit.
- Product brief: `docs/product-brief.md`
- Current task: `specs/first-feature.md`

## Commands
- Install dependencies: `uv sync`
- Run the app: `uv run streamlit run app.py`
- Run the tests: `uv run pytest`

## Structure
- `app.py`: Streamlit screens (UI only). Calls `logic.py` and `db.py`, contains no game rules.
- `logic.py`: game rules (no UI, no database code), including the `CONFIG` dict.
- `db.py`: SQLite storage. The database file is `data/game.db`.
- `tests/`: pytest tests. Tests use a temporary database (`tmp_path`), never `data/game.db`.
- `docs/product-brief.md`: Campus Tycoon BRD (source of truth).
- `specs/`: task specs (Why / What / Out of scope / Done when).

## Code rules
- Money is integer cents.
- Invalid actions raise a clear error in `logic.py` and change nothing in the saved state.
- Never commit `data/`, `*.db`, `.env` or other secrets.

## Branch rules
- Never work directly on `main`. One branch per spec, named after it (for example `first-feature`).
- Work only on the workflow in the current spec. Do not build features from later sections of the brief.
- Do not commit, push or merge unless asked.

## Test and verification rules
- Tests come first: propose them, wait for review, then implement.
- Reviewed tests are the acceptance checks. Never weaken, skip or delete them to make the implementation pass.
- If a test looks wrong, stop and explain why against `docs/product-brief.md`. Change it only after explicit approval.
- Before reporting a task as done:
  1. run `uv run pytest` and show the full output,
  2. list the changed files,
  3. explain how to verify the workflow in the running app, including stopping and restarting it.
