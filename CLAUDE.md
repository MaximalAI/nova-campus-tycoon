# CLAUDE.md

Claude Code reads this file automatically. The project rules live in AGENTS.md and apply in full:

@AGENTS.md

## Additional rules for Claude Code
- Source of truth for requirements: `docs/product-brief.md`. The current task is the spec named in the prompt (for example `specs/first-feature.md`).
- If a requirement cannot be determined from these files, ask instead of guessing.
- Always use uv: `uv sync`, `uv run pytest`, `uv run streamlit run app.py`. Do not use pip directly.
- Push only the feature branch named in the prompt. Never push to or merge into `main`.
