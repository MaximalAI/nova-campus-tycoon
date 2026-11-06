# Claude Code prompts: first feature

Use these prompts one after another in Claude Code. Read each answer before sending the next prompt. You are responsible for the expected outcomes, even if AI writes the tests.

## Prompt 1: Plan and propose tests (no code yet)

```
Read CLAUDE.md, AGENTS.md, docs/product-brief.md and specs/first-feature.md.

Do not implement anything yet, do not create a branch and do not commit.

1. List the state this workflow needs, what must be saved in SQLite, and the rule that rejects an invalid action.
2. Propose the file structure: which functions go into logic.py, which functions and tables into db.py, and which screens into app.py.
3. Propose pytest tests for the allowed action, the rejected actions, and restarting the app (loading the game again from the same database file). Map each test to a "Done when" check in the spec.
4. Point out any requirement you cannot determine from these files.
```

Then compare the proposal with `docs/product-brief.md` and `specs/first-feature.md`. Check every expected number (balance, inventory) yourself.

## Prompt 2: Write the reviewed tests

```
Create the branch first-feature from main.

Write the tests you proposed into tests/, with these corrections: <your corrections, or "none">.

Do not implement logic.py, db.py or app.py yet. Run uv run pytest and show the output; the new tests are expected to fail at this point.

Commit the tests with the message "Add acceptance tests for first feature" and push the branch first-feature.
```

Read the tests on GitHub before continuing. From now on these expectations are fixed.

## Prompt 3: Implement the feature

```
Implement specs/first-feature.md on the branch first-feature.

Use the reviewed tests in tests/ as the acceptance checks. Do not weaken, skip, or delete them to make the implementation pass. If you think a test is wrong, stop and explain why against docs/product-brief.md instead of changing it.

Work only on this workflow. Run uv run pytest, show the final output, and list the changed files.

Then tell me how to verify the workflow in the running app, including stopping and restarting it.

Commit with a clear message and push the branch first-feature. Do not merge into main.
```

## After Claude Code is done
1. In GitHub Desktop: Fetch origin, switch to the branch `first-feature`.
2. In the terminal: `uv sync`, `uv run pytest`, then `uv run streamlit run app.py`.
3. Do the allowed purchase and a rejected purchase yourself.
4. Stop the app (Ctrl+C), start it again, click "Continue" and check that balance and inventory are unchanged. Refreshing the browser alone is not the full persistence check.
5. Read the diff, then open a pull request on GitHub, review it and merge it into `main`.
